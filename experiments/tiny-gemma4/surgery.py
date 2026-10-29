"""Physically cut a Gemma 4 text model: keep some layers, narrow every FFN, keep some vocab rows.

    student = cut(text_model, lm_head, keep_layers, ffn_frac, channel_scores, keep_ids)

Layer removal respects KV sharing: the last `num_kv_shared_layers` layers reuse the keys/values of the last
non-shared layer of their attention type, so those source layers must be kept (stage1.Surgery.protected()).
After the cut, the kept shared layers are still the last ones, so they keep reading from the same sources.
"""
import torch


def cut(text_model, keep_layers, ffn_frac=1.0, channel_scores=None, keep_ids=None, hidden_keep=None):
    """hidden_keep: indices of the hidden (residual) dimensions to keep (Minitron-style embedding-channel pruning).
    Note: Gemma scales input embeddings by sqrt(hidden_size), so a narrower model scales them by a smaller
    factor; RMSNorms make most of the network insensitive to that, and healing absorbs the rest."""
    from transformers.models.gemma4.modeling_gemma4 import Gemma4TextModel
    cfg = text_model.config
    L = cfg.num_hidden_layers
    keep_layers = sorted(keep_layers)
    first_shared = L - (cfg.num_kv_shared_layers or 0)
    # Rebuild the config: per-layer overrides (e.g. head_dim of full-attention layers) are keyed by layer
    # index, so they're renumbered to the kept layers' new positions.
    from transformers import Gemma4TextConfig
    d = cfg.to_dict()
    plc = {int(k): v for k, v in (d.get("per_layer_config") or {}).items()}   # keys may be zero-padded ("04")
    d["per_layer_config"] = {str(j): plc[i] for j, i in enumerate(keep_layers) if i in plc} or None
    d["num_hidden_layers"] = len(keep_layers)
    d["layer_types"] = [cfg.layer_types[i] for i in keep_layers]
    d["num_kv_shared_layers"] = sum(1 for i in keep_layers if i >= first_shared)
    d["intermediate_size"] = max(8, int(round(cfg.intermediate_size * ffn_frac)))
    if keep_ids is not None:
        d["vocab_size"] = d["vocab_size_per_layer_input"] = len(keep_ids)
    if hidden_keep is not None:
        d["hidden_size"] = len(hidden_keep)
    for k in ("transformers_version", "model_type", "architectures"):
        d.pop(k, None)
    new = Gemma4TextConfig(**d)
    dtype = next(text_model.parameters()).dtype
    student = Gemma4TextModel(new).to(dtype)
    ids = torch.tensor(keep_ids) if keep_ids is not None else None
    dev = next(text_model.parameters()).device

    def rows(w):
        return w if ids is None else w[ids.to(w.device)]

    H = cfg.hidden_size
    K = torch.tensor(sorted(hidden_keep), device=dev) if hidden_keep is not None else torch.arange(H, device=dev)
    P = cfg.hidden_size_per_layer_input or 0
    sel = torch.cat([torch.arange(i * P, (i + 1) * P) for i in keep_layers]).to(dev) if P else None

    def put(dst, src):
        if dst.shape != src.shape:
            raise RuntimeError(f"shape {tuple(src.shape)} -> {tuple(dst.shape)}")
        dst.copy_(src.to(dst.dtype).cpu())

    with torch.no_grad():
        T = text_model
        put(student.embed_tokens.weight, rows(T.embed_tokens.weight)[:, K])
        put(student.norm.weight, T.norm.weight[K])
        if P:
            put(student.embed_tokens_per_layer.weight, rows(T.embed_tokens_per_layer.weight)[:, sel])
            put(student.per_layer_model_projection.weight, T.per_layer_model_projection.weight[sel][:, K])
            put(student.per_layer_projection_norm.weight, T.per_layer_projection_norm.weight)
        for j, i in enumerate(keep_layers):
            src, dst = T.layers[i], student.layers[j]
            for n in ("input_layernorm", "post_attention_layernorm", "pre_feedforward_layernorm", "post_feedforward_layernorm"):
                put(getattr(dst, n).weight, getattr(src, n).weight[K])
            if P:
                put(dst.post_per_layer_input_norm.weight, src.post_per_layer_input_norm.weight[K])
                put(dst.per_layer_input_gate.weight, src.per_layer_input_gate.weight[:, K])
                put(dst.per_layer_projection.weight, src.per_layer_projection.weight[K])
            a, b = src.self_attn, dst.self_attn
            put(b.q_proj.weight, a.q_proj.weight[:, K])
            put(b.o_proj.weight, a.o_proj.weight[K])
            put(b.q_norm.weight, a.q_norm.weight)
            if getattr(b, "k_proj", None) is not None:
                put(b.k_proj.weight, a.k_proj.weight[:, K])
                put(b.k_norm.weight, a.k_norm.weight)
                if getattr(b, "v_proj", None) is not None:
                    put(b.v_proj.weight, a.v_proj.weight[:, K])
            for bias in ("q_proj", "k_proj", "v_proj"):
                if getattr(getattr(a, bias, None), "bias", None) is not None:
                    put(getattr(b, bias).bias, getattr(a, bias).bias)
            if getattr(a.o_proj, "bias", None) is not None:
                put(b.o_proj.bias, a.o_proj.bias[K])
            dst.layer_scalar.copy_(src.layer_scalar.cpu())
            # FFN: keep the highest-scoring channels.
            I_dst = dst.mlp.gate_proj.weight.shape[0]
            if channel_scores is not None and I_dst < src.mlp.gate_proj.weight.shape[0]:
                ch = channel_scores[i].topk(I_dst).indices.sort().values.to(dev)
            else:
                ch = torch.arange(I_dst, device=dev)
            put(dst.mlp.gate_proj.weight, src.mlp.gate_proj.weight[ch][:, K])
            put(dst.mlp.up_proj.weight, src.mlp.up_proj.weight[ch][:, K])
            put(dst.mlp.down_proj.weight, src.mlp.down_proj.weight[K][:, ch])
        # Everything trainable must have come from the teacher.
        n_t = sum(p.numel() for p in student.parameters())
    return student

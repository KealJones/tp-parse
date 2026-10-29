"""Physically cut a Gemma 4 text model: keep some layers, narrow every FFN, keep some vocab rows.

    student = cut(text_model, lm_head, keep_layers, ffn_frac, channel_scores, keep_ids)

Layer removal respects KV sharing: the last `num_kv_shared_layers` layers reuse the keys/values of the last
non-shared layer of their attention type, so those source layers must be kept (stage1.Surgery.protected()).
After the cut, the kept shared layers are still the last ones, so they keep reading from the same sources.
"""
import torch


def cut(text_model, keep_layers, ffn_frac=1.0, channel_scores=None, keep_ids=None):
    from transformers.models.gemma4.modeling_gemma4 import Gemma4TextModel
    cfg = text_model.config
    L = cfg.num_hidden_layers
    keep_layers = sorted(keep_layers)
    first_shared = L - (cfg.num_kv_shared_layers or 0)
    # Rebuild the config: per-layer overrides (e.g. head_dim of full-attention layers) are keyed by layer
    # index, so they're renumbered to the kept layers' new positions.
    from transformers import Gemma4TextConfig
    d = cfg.to_dict()
    plc = d.get("per_layer_config") or {}
    d["per_layer_config"] = {str(j): plc[str(i)] for j, i in enumerate(keep_layers) if str(i) in plc} or None
    d["num_hidden_layers"] = len(keep_layers)
    d["layer_types"] = [cfg.layer_types[i] for i in keep_layers]
    d["num_kv_shared_layers"] = sum(1 for i in keep_layers if i >= first_shared)
    d["intermediate_size"] = max(8, int(round(cfg.intermediate_size * ffn_frac)))
    if keep_ids is not None:
        d["vocab_size"] = d["vocab_size_per_layer_input"] = len(keep_ids)
    for k in ("transformers_version", "model_type", "architectures"):
        d.pop(k, None)
    new = Gemma4TextConfig(**d)
    dtype = next(text_model.parameters()).dtype
    student = Gemma4TextModel(new).to(dtype)
    ids = torch.tensor(keep_ids) if keep_ids is not None else None
    dev = next(text_model.parameters()).device

    def rows(w):
        return w if ids is None else w[ids.to(w.device)]

    with torch.no_grad():
        student.embed_tokens.weight.copy_(rows(text_model.embed_tokens.weight).cpu())
        student.norm.load_state_dict(text_model.norm.state_dict())
        P = cfg.hidden_size_per_layer_input or 0
        if P:
            sel = torch.cat([torch.arange(i * P, (i + 1) * P) for i in keep_layers])
            student.embed_tokens_per_layer.weight.copy_(rows(text_model.embed_tokens_per_layer.weight)[:, sel.to(dev)].cpu())
            student.per_layer_model_projection.weight.copy_(text_model.per_layer_model_projection.weight[sel.to(dev)].cpu())
            student.per_layer_projection_norm.load_state_dict(text_model.per_layer_projection_norm.state_dict())
        for j, i in enumerate(keep_layers):
            src, dst = text_model.layers[i], student.layers[j]
            sd = {k: v for k, v in src.state_dict().items() if not k.startswith("mlp.")}
            missing, unexpected = dst.load_state_dict(sd, strict=False)
            bad = [k for k in missing if not k.startswith("mlp.")]
            if bad or unexpected:
                raise RuntimeError(f"layer {i}->{j}: missing {bad} unexpected {unexpected}")
            # FFN: keep the highest-scoring channels.
            I_dst = dst.mlp.gate_proj.weight.shape[0]
            if channel_scores is not None and I_dst < src.mlp.gate_proj.weight.shape[0]:
                ch = channel_scores[i].topk(I_dst).indices.sort().values.to(dev)
            else:
                ch = torch.arange(I_dst, device=dev)
            dst.mlp.gate_proj.weight.copy_(src.mlp.gate_proj.weight[ch].cpu())
            dst.mlp.up_proj.weight.copy_(src.mlp.up_proj.weight[ch].cpu())
            dst.mlp.down_proj.weight.copy_(src.mlp.down_proj.weight[:, ch].cpu())
    return student

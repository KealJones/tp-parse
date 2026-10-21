# The corpora behind the tiny experiments

## Test 1 (the first run): the whole 'corpus' was four labelled pairs

    telo  -> WET
    moku  -> EAT
    water -> WET
    food  -> EAT

There were no sentences. Both languages pointed at the same two labels, so the link between
telo and water was handed to the model. That's why it 'knew'.

## Test 2: sentences only, no labels

Every model only ever predicts the next word. It never sees a label, a translation pair,
or both languages side by side. The toki pona and English stories are generated from
*different* random seeds, so they aren't translations of each other either. They're just
two languages describing the same small world.

### toki pona (pretraining, 4,000 sentences)

    pan li pona .
    waso li moku e kili .
    jan li ike .
    jan li tawa tomo .
    jan lili li lili .
    waso li moku e pan .
    waso li moku e kili .
    waso li tawa kasi suli .
    soweli lili li lili .
    jan lili li olin e waso .
    kili li suwi .
    waso li lape lon kasi suli .
    waso li moku e kili .
    kili li suwi .
    waso li moku e kili .

### English (25 to 400 sentences)

    the bread is good .
    the bird eats the fruit .
    the person is bad .
    the person goes to the house .
    the child is small .
    the bird eats the bread .
    the bird eats the fruit .
    the bird goes to the tree .
    the cat is small .
    the child loves the bird .
    the fruit is sweet .
    the bird sleeps in the tree .
    the bird eats the fruit .
    the fruit is sweet .
    the bird eats the fruit .

### Control: toki pona grammar, random meanings

    soweli li ike .
    jan lili li moku e kili .
    kala li moku e telo .
    kili li moku e soweli lili .
    jan lili li moku e pan .
    jan lili li lili .
    kili li moku e pan .
    telo li moku e jan lili .
    tomo li tawa tomo .
    telo li moku e telo .
    jan li lili .
    kili li moku e soweli .
    pan li lape lon soweli .
    jan lili li olin e telo .
    kili li lape lon tomo .

### Control: random toki pona words

    kasi olin tomo ike jan .
    moku tawa ike .
    ike jan pan pan .
    li jan suwi .
    ike tawa kala li tomo tomo .
    tawa tawa olin .
    li ike suwi .
    lon pan kasi suwi .
    tawa lon suwi .
    kala tawa tawa tomo .
    moku kala suwi jan .
    telo lape soweli .
    lukin pona tawa pona moku lon .
    kili li jan tawa .
    suli soweli lukin pona lon .


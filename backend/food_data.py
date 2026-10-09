"""Reference food table: typical values for ONE serving of common Indian and global foods.

HONEST LABELLING: these are Bubbles reference ESTIMATES compiled from typical published values (Indian Food Composition
Tables 2017, USDA FoodData Central, common packaged-food labels). Real dishes vary 20-40% with recipe, oil and portion,
so every result is shown as a range and nothing here is a measurement. ``verified`` is False for every row until a
dietitian has checked it (see docs/clinical/BUBBLES_CLINICAL_REVIEW_PACKET.md section 12).

Row format (pipe separated):  name | aliases(,) | category | unit | grams | kcal | protein | carbs | fat | fibre | diet | allergens
  unit      the household unit one serving is counted in (piece, katori, cup, glass, tbsp, tsp, slice, bowl, plate, g)
  diet      V vegan, v vegetarian (dairy ok), e eggetarian (contains egg), n non-vegetarian
  allergens letters: g gluten, d dairy, e egg, p peanut, t tree nut, s soy, f fish, c shellfish, w sesame, m mustard
"""
from __future__ import annotations

_RAW = """
roti|chapati,phulka,fulka,indian flatbread|bread|piece|30|100|3.1|18|2.5|2.7|V|g
paratha|plain paratha|bread|piece|60|180|4|26|7|2.5|v|g
aloo paratha|potato paratha|bread|piece|100|260|6|38|10|3|v|g
paneer paratha|paneer stuffed paratha|bread|piece|110|300|10|34|14|3|v|gd
gobi paratha|cauliflower paratha|bread|piece|100|240|6|34|9|3.5|v|g
methi thepla|thepla|bread|piece|35|105|3|15|4|2|v|g
naan|plain naan|bread|piece|90|260|8|45|5|2|v|gd
butter naan|garlic naan|bread|piece|100|320|8|46|11|2|v|gd
tandoori roti|tandoor roti|bread|piece|50|120|4|24|1|3|V|g
missi roti|besan roti|bread|piece|40|120|5|18|3.5|3|V|g
makki di roti|makki roti,corn roti|bread|piece|60|150|3|28|3|3|V|
bajra roti|pearl millet roti|bread|piece|40|115|3.5|21|2.5|3|V|
jowar roti|jowar bhakri,sorghum roti,bhakri|bread|piece|40|110|3|22|1|3|V|
ragi roti|ragi mudde roti,finger millet roti|bread|piece|50|130|3|25|1.5|3|V|
puri|poori|bread|piece|25|100|2|12|5|0.8|V|g
bhatura|bhature|bread|piece|80|270|6|38|10|1.5|v|gd
kulcha|amritsari kulcha|bread|piece|90|250|7|42|6|2|v|gd
white bread|bread slice,bread|bread|slice|25|66|2|12|0.8|0.7|v|g
brown bread|whole wheat bread,multigrain bread|bread|slice|28|70|3|12|1|2|V|g
pav|ladi pav,dinner roll|bread|piece|40|120|3.5|21|2|1|v|g
rice|white rice,cooked rice,steamed rice,plain rice|rice|katori|140|180|3.8|40|0.4|0.6|V|
brown rice|cooked brown rice|rice|katori|140|155|3.5|33|1.2|2.4|V|
jeera rice|cumin rice|rice|katori|150|215|4|38|5|1|v|
vegetable pulao|veg pulao,pulao|rice|katori|200|280|6|45|8|3|v|
vegetable biryani|veg biryani|rice|plate|250|370|8|56|12|4|v|d
chicken biryani|biryani|rice|plate|300|480|24|56|17|2|n|d
mutton biryani|lamb biryani|rice|plate|300|530|26|55|22|2|n|d
egg biryani||rice|plate|280|440|16|56|16|3|e|de
khichdi|dal khichdi,moong khichdi|rice|katori|200|230|8|38|5|3|v|
curd rice|thayir sadam,dahi chawal|rice|katori|200|250|7|36|8|1|v|d
lemon rice|chitranna|rice|katori|180|280|5|44|9|2|V|p
tamarind rice|puliyogare,pulihora|rice|katori|180|300|5|46|10|3|V|p
tomato rice||rice|katori|180|260|5|44|7|2|V|
vegetable fried rice|veg fried rice,fried rice|rice|plate|200|320|7|48|10|2|V|s
egg fried rice||rice|plate|220|370|12|50|13|2|e|es
bisi bele bath|bisibelebath|rice|katori|250|350|10|55|9|6|V|
poha|flattened rice,aval,kanda poha|breakfast|katori|150|180|3.5|32|4.5|2|V|p
upma|rava upma,suji upma|breakfast|katori|200|220|5|32|8|2|V|g
semiya upma|vermicelli upma|breakfast|katori|200|230|5|36|7|2|V|g
idli|idly|breakfast|piece|40|58|2|12|0.4|0.6|V|
plain dosa|dosa|breakfast|piece|90|150|3.5|25|4|1|V|
masala dosa||breakfast|piece|180|290|6|45|9|3|V|
rava dosa||breakfast|piece|110|190|4|28|7|1.5|V|g
set dosa||breakfast|piece|60|110|3|19|2.5|1|V|
uttapam|uthappam|breakfast|piece|120|190|6|29|5|2|V|
medu vada|vada,uzhunnu vada|breakfast|piece|40|110|3.5|10|6.5|1.5|V|
appam||breakfast|piece|60|120|2|24|1.5|0.6|V|
idiyappam|string hoppers|breakfast|piece|70|110|2|24|0.5|1|V|
puttu||breakfast|piece|100|150|3|30|2|2|V|
dhokla|khaman dhokla|breakfast|piece|50|60|2.5|9|1.5|1|v|
besan chilla|besan cheela,chilla|breakfast|piece|60|130|6|15|5|3|V|
moong dal chilla|moong chilla|breakfast|piece|60|110|7|14|3|3|V|
thalipeeth||breakfast|piece|80|180|5|25|7|4|V|
sabudana khichdi|sabudana,sago khichdi|breakfast|katori|150|300|3|45|12|1|V|p
pesarattu|moong dosa|breakfast|piece|100|140|7|20|3.5|3|V|
oats|rolled oats,oatmeal|breakfast|g|40|150|5.3|26|2.6|4|V|g
oats porridge|porridge|breakfast|bowl|250|180|7|28|4|4|v|gd
daliya|broken wheat porridge|breakfast|katori|200|170|6|32|2|5|V|g
cornflakes|corn flakes|breakfast|g|30|110|2|25|0.3|0.8|V|g
muesli||breakfast|g|40|150|4|27|3|3|V|gt
granola||breakfast|g|40|190|4|26|8|3|V|gt
moong dal|yellow moong dal|dal|katori|150|130|9|19|2|4|V|
toor dal|arhar dal,tuvar dal,dal,daal,lentils,dal tadka|dal|katori|150|150|8|21|4|4|V|
masoor dal|red lentil dal|dal|katori|150|140|9|20|2.5|4|V|
chana dal||dal|katori|150|180|10|27|3.5|6|V|
urad dal|black gram dal|dal|katori|150|170|10|25|3|5|V|
dal fry||dal|katori|150|180|8|21|7|4|V|
dal makhani||dal|katori|150|240|9|20|13|5|v|d
palak dal|spinach dal|dal|katori|150|140|8|19|3.5|5|V|
sambar||dal|katori|150|90|4|13|2.5|3|V|
rasam||dal|katori|150|40|1.5|7|1|1|V|
rajma|rajma masala,kidney beans|dal|katori|150|190|9|28|4|7|V|
chole|chana masala,chickpea curry|dal|katori|150|220|9|28|8|7|V|
lobia|black eyed peas curry|dal|katori|150|160|8|25|3|6|V|
kadhi|punjabi kadhi,gujarati kadhi|dal|katori|150|130|4|10|8|0.5|v|d
sprouts|moong sprouts,sprout salad|dal|katori|100|90|7|14|0.7|3|V|
boiled chana|kala chana,chickpeas boiled|dal|katori|100|165|9|27|2.6|7.6|V|
hummus||dal|tbsp|30|70|2|5|5|1.5|V|w
aloo gobi||curry|katori|150|160|3|18|8|3|V|
aloo sabzi|aloo ki sabzi,potato curry|curry|katori|150|190|3|26|8|3|V|
jeera aloo|aloo jeera|curry|katori|120|170|2.5|24|7|2.5|V|
dum aloo||curry|katori|150|230|3.5|26|13|3|v|
bhindi masala|bhindi,okra sabzi|curry|katori|120|120|3|10|8|3.5|V|
baingan bharta|baingan,brinjal|curry|katori|150|130|3|12|8|4|V|
mixed vegetable|mixed veg,sabzi,veg curry,vegetable curry|curry|katori|150|130|3|14|7|4|V|
lauki sabzi|bottle gourd sabzi|curry|katori|150|80|2|9|4|2.5|V|
cabbage sabzi|patta gobi sabzi,cabbage poriyal|curry|katori|120|90|2.5|9|5|3|V|
beans poriyal|green beans sabzi|curry|katori|100|80|2.5|9|4|3|V|
palak paneer||curry|katori|150|250|11|8|19|3|v|d
paneer butter masala|butter paneer|curry|katori|150|330|12|10|28|2|v|dt
kadai paneer||curry|katori|150|280|12|9|22|2.5|v|d
matar paneer||curry|katori|150|260|11|11|19|3|v|d
shahi paneer||curry|katori|150|340|12|10|28|2|v|dt
paneer bhurji||curry|katori|100|230|14|5|17|1|v|d
malai kofta||curry|katori|150|330|8|20|25|2|v|dt
veg korma|vegetable korma|curry|katori|150|220|5|15|16|3|v|dt
mushroom masala|mushroom curry|curry|katori|150|130|5|10|8|2|V|
soya chunks curry|soya chunk curry|curry|katori|150|190|16|12|8|5|V|s
tofu bhurji|scrambled tofu|curry|katori|100|150|11|4|10|1.5|V|s
sarson ka saag|sarson saag|curry|katori|150|150|6|10|9|5|v|d
gobi manchurian||curry|katori|150|260|5|28|14|3|V|s
chicken curry|murgh curry,chicken masala|nonveg|katori|150|230|20|6|14|1|n|
butter chicken|murgh makhani|nonveg|katori|150|320|18|9|24|1|n|dt
chicken tikka masala||nonveg|katori|150|290|20|10|19|1|n|d
chicken tikka||nonveg|piece|100|150|24|3|5|0.5|n|d
tandoori chicken||nonveg|piece|150|260|30|4|13|0.5|n|d
chicken 65||nonveg|piece|100|250|18|10|15|0.5|n|ge
chicken kebab|seekh kebab|nonveg|piece|60|140|10|3|10|0.5|n|
mutton curry|lamb curry,mutton masala,gosht|nonveg|katori|150|300|20|5|22|1|n|
keema|mutton keema,minced meat curry|nonveg|katori|150|300|18|6|22|1.5|n|
fish curry|machli curry,meen curry|nonveg|katori|150|210|19|5|12|0.8|n|f
fish fry|fried fish|nonveg|piece|100|220|19|8|12|0.5|n|f
prawn curry|shrimp curry,jhinga curry|nonveg|katori|150|190|18|5|10|0.8|n|c
egg curry||nonveg|katori|200|280|14|8|21|1.5|e|e
boiled egg|egg,eggs,hard boiled egg|protein|piece|50|75|6.3|0.6|5|0|e|e
omelette|egg omelette,omelet,masala omelette|protein|piece|120|190|13|2|15|0.5|e|e
egg bhurji|scrambled eggs,anda bhurji|protein|katori|100|190|12|2|15|0.5|e|e
fried egg|sunny side up,egg fry|protein|piece|46|90|6.3|0.4|7|0|e|e
chicken breast|grilled chicken,boiled chicken|protein|g|100|165|31|0|3.6|0|n|
chicken thigh|chicken leg|protein|g|100|210|26|0|11|0|n|
mutton|lamb meat,goat meat|protein|g|100|220|25|0|13|0|n|
rohu|rohu fish,fish|protein|g|100|97|17|0|2.7|0|n|f
salmon||protein|g|100|208|20|0|13|0|n|f
tuna canned|tuna|protein|g|100|116|26|0|1|0|n|f
prawns|shrimp|protein|g|100|99|24|0.2|0.3|0|n|c
paneer|cottage cheese|protein|g|100|265|18|1.2|21|0|v|d
tofu||protein|g|100|76|8|2|4.8|0.3|V|s
soya chunks|soy chunks,nutrela,meal maker|protein|g|30|104|15.6|10|0.2|4|V|s
tempeh||protein|g|100|190|20|8|11|0|V|s
whey protein|protein powder,protein shake,whey|protein|scoop|30|120|24|3|1.5|0|v|d
greek yogurt|hung curd,greek yoghurt|dairy|g|100|59|10|3.6|0.4|0|v|d
milk|full fat milk,whole milk,doodh|dairy|glass|250|160|8|12|8|0|v|d
toned milk|toned|dairy|glass|250|140|7.5|12|5.5|0|v|d
skimmed milk|skim milk,double toned milk|dairy|glass|250|90|8.5|12|0.3|0|v|d
almond milk|plant milk|dairy|glass|250|40|1|2|3|0.5|V|t
soy milk|soya milk|dairy|glass|250|100|7|8|4|1|V|s
curd|dahi,yogurt,yoghurt,plain curd|dairy|katori|150|98|5.4|7|5|0|v|d
raita|boondi raita,cucumber raita,veg raita|dairy|katori|100|70|3|5|4|0.5|v|d
lassi|sweet lassi|dairy|glass|250|200|6|32|5|0|v|d
chaas|buttermilk,salted lassi,mattha|dairy|glass|250|40|2|3|1.5|0|v|d
cheese|cheddar,processed cheese|dairy|slice|20|66|4|0.5|5.5|0|v|d
mozzarella||dairy|g|30|85|6|0.7|6|0|v|d
ghee|clarified butter|fat|tsp|5|45|0|0|5|0|v|d
butter||fat|tsp|5|36|0|0|4|0|v|d
oil|cooking oil,refined oil,mustard oil,sunflower oil|fat|tsp|5|45|0|0|5|0|V|
olive oil||fat|tsp|5|45|0|0|5|0|V|
coconut oil||fat|tsp|5|45|0|0|5|0|V|
mayonnaise|mayo|fat|tbsp|15|100|0.2|0.5|11|0|e|e
peanut butter||fat|tbsp|16|95|3.5|3|8|1|V|p
apple||fruit|piece|180|95|0.5|25|0.3|4.4|V|
banana|kela|fruit|piece|120|105|1.3|27|0.4|3.1|V|
mango|aam|fruit|piece|200|130|1.8|33|0.8|3.6|V|
orange|santra|fruit|piece|130|62|1.2|15|0.2|3.1|V|
sweet lime|mosambi|fruit|piece|130|50|1|11|0.2|2|V|
papaya|papita|fruit|katori|150|60|0.7|15|0.2|2.5|V|
guava|amrood|fruit|piece|100|68|2.6|14|1|5.4|V|
watermelon|tarbooj|fruit|slice|280|85|1.7|21|0.4|1.1|V|
muskmelon|kharbuja,cantaloupe|fruit|katori|150|50|1.2|12|0.3|1.4|V|
grapes|angur|fruit|katori|100|69|0.7|18|0.2|0.9|V|
pomegranate|anar|fruit|katori|100|83|1.7|19|1.2|4|V|
pineapple|ananas|fruit|katori|100|50|0.5|13|0.1|1.4|V|
pear|nashpati|fruit|piece|170|98|0.6|26|0.2|5.5|V|
kiwi||fruit|piece|75|45|0.8|11|0.4|2.3|V|
strawberries|strawberry|fruit|katori|100|32|0.7|7.7|0.3|2|V|
chikoo|sapota|fruit|piece|100|83|0.4|20|1.1|5.3|V|
dates|khajur|fruit|piece|24|66|0.4|18|0|1.6|V|
raisins|kishmish|fruit|tbsp|20|60|0.6|16|0.1|0.8|V|
coconut|fresh coconut,nariyal|fruit|piece|30|106|1|5|10|2.7|V|
almonds|badam|nuts|piece|12|70|2.5|2.6|6|1.5|V|t
cashews|cashew nuts,kaju|nuts|piece|15|85|2.8|4.6|7|0.5|V|t
walnuts|akhrot|nuts|piece|14|92|2.1|1.9|9|1|V|t
pistachios|pista|nuts|piece|15|85|3|4|7|1.7|V|t
peanuts|groundnuts,roasted peanuts,moongphali|nuts|g|30|170|7.7|5|14.5|2.5|V|p
makhana|fox nuts,lotus seeds,phool makhana|nuts|g|30|105|3|22|0.2|1.5|V|
roasted chana|bhuna chana,chana|nuts|g|30|110|6|18|1.5|5|V|
chia seeds|chia|nuts|tbsp|12|58|2|5|3.7|4|V|
flax seeds|alsi,flaxseed|nuts|tbsp|10|55|1.9|3|4.2|2.7|V|
sunflower seeds||nuts|tbsp|10|58|2|2|5|1|V|
cucumber|kheera|vegetable|g|100|15|0.7|3.6|0.1|0.5|V|
tomato|tamatar|vegetable|piece|100|18|0.9|3.9|0.2|1.2|V|
onion|pyaz|vegetable|piece|50|20|0.5|4.7|0.1|0.8|V|
carrot|gajar|vegetable|piece|60|25|0.6|5.8|0.1|1.7|V|
beetroot|chukandar|vegetable|piece|80|35|1.3|8|0.1|2|V|
spinach|palak|vegetable|katori|100|23|2.9|3.6|0.4|2.2|V|
broccoli||vegetable|katori|100|35|2.4|7|0.4|2.6|V|
cauliflower|gobi|vegetable|katori|100|25|1.9|5|0.3|2|V|
green salad|salad,kachumber,mixed salad|vegetable|bowl|150|35|1.5|7|0.3|2.5|V|
potato boiled|boiled potato,aloo|vegetable|piece|150|130|3|30|0.2|3.3|V|
sweet potato|shakarkandi|vegetable|piece|130|112|2|26|0.1|3.8|V|
sweet corn|corn,bhutta,corn on the cob|vegetable|piece|90|100|3.4|21|1.3|2.4|V|
green peas|matar|vegetable|katori|80|65|4.3|11|0.3|4.4|V|
mushrooms|mushroom|vegetable|katori|100|22|3.1|3.3|0.3|1|V|
samosa|aloo samosa|snack|piece|100|260|4|28|15|2|V|g
kachori|dal kachori|snack|piece|80|250|5|26|14|2.5|V|g
pakora|bhajiya,bhajia,pakoda,onion pakora|snack|piece|20|50|1.3|5|3|0.8|V|
bread pakora||snack|piece|80|230|6|25|12|1.5|v|g
aloo tikki|tikki|snack|piece|100|190|3|25|9|2.5|V|g
vada pav|wada pav|snack|piece|120|300|7|45|10|3|V|g
pav bhaji||snack|plate|250|400|9|55|16|6|v|gd
misal pav|misal|snack|plate|250|380|12|52|13|8|V|g
bhel puri|bhel|snack|bowl|100|160|4|27|4|3|V|gp
pani puri|golgappa,puchka|snack|piece|20|33|0.6|5|1.3|0.5|V|g
sev puri||snack|plate|100|220|4|26|11|3|V|gp
dahi puri||snack|plate|120|210|5|28|8|2|v|gd
dahi vada|dahi bhalla|snack|piece|90|130|5|15|5|1|v|d
khakhra||snack|piece|25|110|3.5|16|3.5|2|V|g
murukku|chakli|snack|g|30|150|2.5|18|7.5|1|V|
namkeen|bhujia,sev,mixture|snack|g|30|160|4|15|9|2|V|p
potato chips|chips,wafers|snack|g|30|160|2|15|10|1|V|
popcorn||snack|g|30|115|3.5|22|1.5|4|V|
french fries|fries|snack|g|100|310|3.5|40|15|3.5|V|
maggi|instant noodles,noodles pack|snack|piece|70|310|7|43|12|2|v|g
chowmein|veg chowmein,hakka noodles|snack|plate|250|410|10|62|13|4|V|gs
pasta|pasta cooked,penne,spaghetti|snack|katori|150|235|8|46|1.4|2.5|V|g
white sauce pasta|creamy pasta|snack|plate|250|420|13|52|18|3|v|gd
pizza|margherita pizza,pizza slice|snack|slice|100|270|11|33|10|2|v|gd
veg burger|aloo tikki burger|snack|piece|150|360|9|50|14|3|v|g
chicken burger||snack|piece|200|430|22|42|19|2|n|ge
veg sandwich|sandwich,grilled sandwich|snack|piece|150|280|8|38|11|3|v|gd
egg sandwich||snack|piece|150|310|13|33|14|2|e|ge
frankie|kathi roll,veg roll,wrap,chicken roll|snack|piece|200|400|14|48|16|3|n|g
shawarma||snack|piece|250|450|25|42|20|3|n|g
momos|steamed momos,veg momos|snack|piece|25|40|1.5|7|1|0.5|V|gs
fried momos||snack|piece|30|70|2|8|3.5|0.5|V|gs
spring roll||snack|piece|80|190|4|22|9|1.5|V|g
biscuit|marie biscuit,biscuits|snack|piece|7|30|0.5|5|0.9|0.1|v|g
digestive biscuit|oat biscuit|snack|piece|15|70|1|10|3|1|v|g
cookie|cookies|snack|piece|12|55|0.6|7.5|2.6|0.3|v|gd
rusk|toast rusk|snack|piece|10|42|1|7.5|1|0.3|v|g
papad|roasted papad|snack|piece|12|40|2.5|6|0.5|1|V|
masala papad|fried papad|snack|piece|25|90|2.5|7|6|1|V|
protein bar|energy bar|snack|piece|60|220|20|22|7|3|v|dt
granola bar|cereal bar|snack|piece|40|180|3|27|7|2|v|gt
peanut chikki|chikki,gajak|snack|piece|25|130|3|16|6|1|V|p
gulab jamun||sweet|piece|40|150|2|22|6|0.2|v|gd
rasgulla|rosogolla|sweet|piece|40|105|3|22|0.6|0|v|d
rasmalai||sweet|piece|70|130|5|14|6|0|v|dt
jalebi||sweet|piece|40|150|1|26|5|0.2|v|g
besan laddu|laddu|sweet|piece|40|190|4|22|10|1.5|v|d
motichoor laddu||sweet|piece|40|170|2|25|7|0.5|v|d
kaju katli|kaju barfi|sweet|piece|20|90|2|10|5|0.4|v|t
barfi|milk barfi,burfi|sweet|piece|30|130|3|17|5.5|0|v|d
sooji halwa|suji halwa,sheera|sweet|katori|100|280|3|36|14|1|v|gd
gajar halwa|carrot halwa|sweet|katori|100|230|4|28|12|1.5|v|dt
kheer|rice kheer,payasam|sweet|katori|150|220|5|34|7|0.5|v|dt
modak||sweet|piece|40|140|2|22|5|1|v|d
puran poli||sweet|piece|80|230|5|42|5|2|v|g
ice cream|vanilla ice cream|sweet|scoop|70|140|2.5|16|7|0.5|v|d
chocolate|dark chocolate,milk chocolate|sweet|g|20|110|1.5|11|7|1.5|v|d
cake|cake slice|sweet|slice|80|300|4|42|13|1|v|gde
sugar|cheeni|sweet|tsp|4|16|0|4|0|0|V|
honey|shahad|sweet|tsp|7|21|0|5.7|0|0|v|
jaggery|gur|sweet|g|10|38|0|9.7|0|0|V|
tea|chai,milk tea,masala chai|drink|cup|150|60|1.5|9|2|0|v|d
tea without sugar|black tea,sugar free chai|drink|cup|150|30|1.5|2|1.5|0|v|d
green tea||drink|cup|200|2|0|0.4|0|0|V|
black coffee||drink|cup|200|3|0.3|0|0|0|V|
coffee|milk coffee,filter coffee|drink|cup|150|70|2|9|2.5|0|v|d
cold coffee||drink|glass|250|200|5|30|7|0|v|d
coconut water|nariyal pani|drink|glass|250|46|1.7|9|0.5|2.6|V|
orange juice|fresh juice,fruit juice,juice|drink|glass|250|112|1.7|26|0.5|0.5|V|
sugarcane juice|ganne ka ras|drink|glass|250|180|0.5|45|0|0|V|
nimbu pani|lemonade,lime water,shikanji|drink|glass|250|80|0.2|20|0|0|V|
cola|soda,soft drink,coke,pepsi|drink|glass|330|140|0|35|0|0|V|
banana shake|banana milkshake|drink|glass|300|250|8|40|7|2|v|d
mango shake|mango lassi,mango milkshake|drink|glass|300|280|7|50|6|1.5|v|d
protein smoothie|smoothie|drink|glass|300|220|20|25|5|3|v|d
water||drink|glass|250|0|0|0|0|0|V|
quinoa|cooked quinoa|grain|katori|150|180|6.6|32|3|3.8|V|
wheat flour|atta|grain|g|30|105|3.5|22|0.6|3|V|g
besan|gram flour|grain|g|30|115|6.5|16|2|3|V|
sooji|semolina,rava|grain|g|30|105|3.5|22|0.4|1|V|g
pickle|achar|condiment|tsp|5|20|0.1|0.5|2|0.2|V|m
green chutney|mint chutney,coriander chutney|condiment|tbsp|15|10|0.5|1.5|0.2|0.5|V|
coconut chutney||condiment|tbsp|30|60|0.8|2|5.5|1.5|V|
tomato ketchup|ketchup,sauce|condiment|tbsp|17|18|0.2|4.5|0|0|V|
sandwich spread|cheese spread|condiment|tbsp|15|40|1|1|3.5|0|v|d
litti chokha|litti,baati chokha|bread|piece|120|230|7|34|7|5|v|gd
dal baati churma|dal baati|bread|plate|300|620|16|75|28|7|v|gd
khandvi|besan khandvi|snack|piece|20|35|1.5|4|1.5|0.5|v|
handvo|gujarati handvo|snack|piece|80|160|6|21|6|3|V|
fafda|fafda gathiya|snack|g|30|150|4|16|8|1|V|
patra|alu vadi,colocasia roll|snack|piece|30|60|2|8|2.5|1.5|V|
undhiyu|gujarati undhiyu|curry|katori|150|220|5|20|13|6|V|p
sev tameta|sev tamatar sabzi|curry|katori|150|190|4|16|12|3|V|
methi aloo|aloo methi|curry|katori|120|150|3|18|7|3|V|
kofta curry|veg kofta curry|curry|katori|150|300|7|18|22|3|v|dt
chilli paneer|paneer chilli|curry|katori|150|320|15|12|24|2|v|ds
paneer tikka|tandoori paneer|snack|piece|25|60|4|1.5|4.5|0.3|v|d
baby corn manchurian|baby corn fry|snack|katori|100|180|3|20|10|2|V|gs
gobi 65|cauliflower 65|snack|katori|100|200|4|20|11|2.5|V|g
chilli chicken|chicken chilli|nonveg|katori|150|320|24|12|20|1|n|gs
schezwan fried rice|schezwan rice|rice|plate|220|370|8|55|13|2|V|gs
hakka noodles veg|veg noodles|snack|plate|250|400|9|60|13|4|V|gs
manchow soup|hot and sour soup,veg soup|drink|bowl|250|90|3|12|3|1.5|V|gs
sweet corn soup|corn soup|drink|bowl|250|110|3|20|2|2|V|
tomato soup|cream of tomato|drink|bowl|250|100|2|15|4|2|v|d
chicken soup|clear chicken soup|drink|bowl|250|90|10|6|3|0.5|n|
thukpa|tibetan noodle soup|snack|bowl|350|320|14|45|9|4|n|g
shami kebab|galouti kebab|nonveg|piece|40|110|7|6|7|1|n|e
rogan josh|mutton rogan josh|nonveg|katori|150|310|21|6|23|1|n|d
keema matar|mutton keema matar|nonveg|katori|150|290|19|10|20|3|n|
chicken korma|murgh korma|nonveg|katori|150|300|20|8|21|1|n|dt
dal gosht|mutton dal|nonveg|katori|150|260|19|12|15|3|n|
haleem|hyderabadi haleem|nonveg|katori|200|330|20|28|15|4|n|g
hyderabadi biryani|hyderabadi dum biryani|rice|plate|300|520|25|58|20|2|n|d
chettinad chicken|chicken chettinad|nonveg|katori|150|280|22|7|18|1.5|n|
malabar fish curry|kerala fish curry|nonveg|katori|150|220|19|5|14|1|n|f
fish tikka|tandoori fish|nonveg|piece|30|55|6|0.8|3|0|n|fd
amritsari fish|fish pakora|nonveg|piece|50|140|10|7|8|0.5|n|fg
macher jhol|bengali fish curry|nonveg|katori|150|200|18|5|12|1|n|fm
kosha mangsho|bengali mutton curry|nonveg|katori|150|330|22|6|24|1|n|
aloo posto|poppy seed potato|curry|katori|120|190|3|20|11|2.5|V|
luchi|bengali luchi|bread|piece|30|110|2|13|6|0.6|V|g
parotta|kerala parotta,paratha layered|bread|piece|80|260|5|36|11|1.5|v|g
appam stew|vegetable stew|curry|katori|150|180|4|14|11|3|V|
avial|kerala avial|curry|katori|150|170|4|13|11|4|v|d
thoran|cabbage thoran,beans thoran|curry|katori|100|110|3|9|7|3.5|V|
kootu|vegetable kootu|curry|katori|150|130|6|15|5|5|V|
mor kuzhambu|buttermilk curry|curry|katori|150|100|3|8|6|0.8|v|d
ven pongal|pongal|breakfast|katori|200|260|8|38|8|2|v|d
sakkarai pongal|sweet pongal|sweet|katori|150|320|5|58|8|1.5|v|dt
rava idli|semolina idli|breakfast|piece|60|90|2.5|15|2|0.8|v|g
kanchipuram idli||breakfast|piece|90|130|4|19|4|1|v|d
neer dosa||breakfast|piece|60|80|1.5|16|1|0.5|V|
pesarattu upma||breakfast|piece|180|250|9|35|8|4|V|
akki roti|rice flour roti|bread|piece|60|160|3|28|4|2|V|
dibba rotti||bread|piece|70|180|5|28|5|2|V|
mishti doi|sweet curd|sweet|katori|100|135|4|20|4.5|0|v|d
sandesh|bengali sandesh|sweet|piece|30|100|4|13|3.5|0|v|d
shrikhand||sweet|katori|100|220|5|35|7|0|v|dt
basundi|rabri,rabdi|sweet|katori|100|250|7|30|11|0|v|dt
peda|milk peda|sweet|piece|25|95|2.5|14|3.5|0|v|d
soan papdi||sweet|piece|25|130|2|16|7|0.5|v|gd
malpua||sweet|piece|50|190|2.5|26|9|0.5|v|gd
imarti||sweet|piece|40|170|1.5|27|6|0.3|V|g
coconut ladoo|nariyal ladoo|sweet|piece|30|120|1.2|14|7|2|v|d
til ladoo|sesame ladoo|sweet|piece|25|120|2.5|12|7|1.5|v|w
chikki||sweet|piece|25|120|2.5|15|6|1|V|p
aam panna|raw mango drink|drink|glass|250|90|0.4|22|0.3|0.5|V|
jaljeera||drink|glass|250|25|0.5|6|0|0.5|V|
thandai||drink|glass|250|230|6|28|10|1|v|dt
rose milk||drink|glass|250|190|7|30|5|0|v|d
hot chocolate|cocoa|drink|cup|250|190|7|27|6|1.5|v|d
masala chai with jaggery|jaggery tea|drink|cup|150|65|1.5|10|2|0|v|d
energy drink||drink|glass|250|110|0|28|0|0|V|
scrambled eggs||protein|katori|100|170|11|2|13|0|e|e
egg white omelette||protein|piece|100|55|11|1|0.3|0|e|e
pancake|pancakes|breakfast|piece|60|150|4|22|5|0.8|v|gde
waffle||breakfast|piece|75|220|6|25|10|1|v|gde
avocado toast||breakfast|piece|120|250|6|22|16|7|V|g
peanut butter toast||breakfast|piece|60|230|8|22|12|3|V|gp
french toast||breakfast|piece|70|180|7|20|8|1|v|gde
cheese sandwich|grilled cheese sandwich|snack|piece|120|330|13|30|18|2|v|gd
paneer sandwich||snack|piece|130|320|13|32|15|3|v|gd
club sandwich||snack|piece|250|520|27|45|25|3|n|ge
caesar salad|chicken caesar|snack|bowl|250|350|22|14|23|3|n|dge
greek salad||snack|bowl|200|220|7|10|18|3|v|d
pasta marinara|red sauce pasta|snack|plate|250|380|13|68|6|5|V|g
lasagna||snack|piece|250|450|24|38|22|3|n|gd
burrito|chicken burrito|snack|piece|300|520|26|60|18|7|n|gd
tacos|taco|snack|piece|100|200|9|18|10|3|n|g
sushi roll|veg sushi|snack|piece|30|45|1.2|9|0.4|0.5|n|f
ramen|instant ramen bowl|snack|bowl|400|450|12|63|17|3|n|gse
pad thai||snack|plate|300|560|22|70|21|4|n|cp
fried chicken||nonveg|piece|100|290|20|10|19|0.5|n|g
grilled fish|baked fish|nonveg|g|100|130|23|0|4|0|n|f
steak|beef steak|nonveg|g|100|250|26|0|16|0|n|
hamburger|beef burger|snack|piece|200|450|25|38|22|2|n|g
hot dog||snack|piece|150|330|11|25|21|1|n|g
falafel wrap|falafel|snack|piece|220|430|14|55|17|8|V|gw
pita bread|pita|bread|piece|60|165|5.5|33|0.7|1.3|V|g
quesadilla||snack|piece|150|380|16|30|21|2|v|gd
garlic bread||bread|slice|40|140|3|18|6|1|v|gd
bagel||bread|piece|95|270|10|53|1.5|2.5|V|g
croissant||bread|piece|60|230|5|26|12|1.5|v|gde
muffin|blueberry muffin|sweet|piece|110|370|5|52|16|1.5|v|gde
doughnut|donut|sweet|piece|60|250|3|30|13|1|v|gde
brownie||sweet|piece|60|240|3|30|13|1.5|v|gde
cheesecake||sweet|slice|100|320|5.5|26|23|0.5|v|gde
oats cookie||snack|piece|25|110|1.5|16|4.5|1|v|gd
trail mix|nuts and raisins|nuts|g|30|150|4|13|10|2|V|pt
dry fruit mix|mixed dry fruits|nuts|g|30|160|4|14|10|2.5|V|t
chia pudding||breakfast|bowl|200|220|7|22|12|9|V|t
smoothie bowl||breakfast|bowl|300|280|8|45|8|7|v|d
"""

# Key micronutrients per serving for the foods where a typical value is well known (mg / mcg / IU). Estimates.
MICROS: dict[str, dict[str, float]] = {
    "roti": {"iron_mg": 1.0, "calcium_mg": 10, "folate_ug": 15},
    "rice": {"iron_mg": 0.4, "folate_ug": 6}, "dal": {}, "toor dal": {"iron_mg": 2.4, "calcium_mg": 40, "folate_ug": 150},
    "moong dal": {"iron_mg": 2.0, "calcium_mg": 35, "folate_ug": 180}, "masoor dal": {"iron_mg": 3.0, "calcium_mg": 30, "folate_ug": 170},
    "rajma": {"iron_mg": 3.0, "calcium_mg": 60, "folate_ug": 120}, "chole": {"iron_mg": 3.0, "calcium_mg": 70, "folate_ug": 150},
    "palak paneer": {"iron_mg": 3.0, "calcium_mg": 280, "folate_ug": 110}, "spinach": {"iron_mg": 2.7, "calcium_mg": 99, "folate_ug": 194},
    "paneer": {"calcium_mg": 480, "b12_ug": 0.8}, "curd": {"calcium_mg": 160, "b12_ug": 0.5}, "milk": {"calcium_mg": 300, "b12_ug": 1.1, "vitd_iu": 100},
    "toned milk": {"calcium_mg": 300, "b12_ug": 1.1, "vitd_iu": 100}, "skimmed milk": {"calcium_mg": 300, "b12_ug": 1.1, "vitd_iu": 100},
    "greek yogurt": {"calcium_mg": 110, "b12_ug": 0.5}, "chaas": {"calcium_mg": 100, "b12_ug": 0.3}, "boiled egg": {"iron_mg": 0.9, "b12_ug": 0.6, "vitd_iu": 41, "folate_ug": 22},
    "chicken breast": {"iron_mg": 1.0, "b12_ug": 0.3}, "mutton": {"iron_mg": 2.7, "b12_ug": 2.5}, "rohu": {"b12_ug": 2.0, "calcium_mg": 650 * 0.1},
    "salmon": {"b12_ug": 3.2, "vitd_iu": 570}, "ragi roti": {"iron_mg": 2.0, "calcium_mg": 175}, "bajra roti": {"iron_mg": 2.5, "calcium_mg": 15},
    "jowar roti": {"iron_mg": 2.0, "calcium_mg": 15}, "almonds": {"calcium_mg": 30, "iron_mg": 0.4}, "tofu": {"calcium_mg": 350, "iron_mg": 2.7},
    "soya chunks": {"iron_mg": 6.0, "calcium_mg": 100}, "beetroot": {"iron_mg": 0.6, "folate_ug": 80}, "orange": {"folate_ug": 40},
    "banana": {"folate_ug": 24}, "guava": {"folate_ug": 49}, "dates": {"iron_mg": 0.2}, "roasted chana": {"iron_mg": 1.5, "folate_ug": 100},
    "sprouts": {"iron_mg": 1.5, "folate_ug": 110}, "chia seeds": {"calcium_mg": 76, "iron_mg": 0.9}, "flax seeds": {"calcium_mg": 26},
    "sesame": {"calcium_mg": 90}, "broccoli": {"calcium_mg": 47, "folate_ug": 63, "iron_mg": 0.7}, "whey protein": {"calcium_mg": 120, "b12_ug": 0.5},
}

CATEGORY_UNIT_GRAMS: dict[str, dict[str, float]] = {
    # grams in one household unit, by food category (cooked weights). Falls back to GENERIC_UNIT_GRAMS.
    "rice": {"katori": 140, "bowl": 200, "plate": 250, "cup": 160, "ladle": 70},
    "dal": {"katori": 150, "bowl": 220, "cup": 240, "ladle": 100, "glass": 250},
    "curry": {"katori": 130, "bowl": 200, "cup": 200, "ladle": 70, "plate": 250},
    "nonveg": {"katori": 150, "bowl": 220, "cup": 200, "ladle": 70},
    "dairy": {"katori": 150, "bowl": 220, "glass": 250, "cup": 245, "ladle": 70},
    "breakfast": {"katori": 150, "bowl": 200, "cup": 180, "plate": 220},
    "grain": {"katori": 150, "bowl": 200, "cup": 160},
    "vegetable": {"katori": 100, "bowl": 150, "cup": 100},
    "fruit": {"katori": 120, "bowl": 180, "cup": 150},
}
GENERIC_UNIT_GRAMS = {"tsp": 5.0, "tbsp": 15.0, "glass": 250.0, "cup": 240.0, "katori": 150.0, "bowl": 220.0, "ladle": 60.0,
                      "handful": 30.0, "plate": 250.0, "g": 1.0, "gram": 1.0, "grams": 1.0, "kg": 1000.0, "ml": 1.0, "l": 1000.0,
                      "litre": 1000.0, "liter": 1000.0, "oz": 28.35, "pinch": 0.5}
# oils/fats are lighter per tbsp than water; they get their own tbsp/tsp grams
FAT_UNIT_GRAMS = {"tsp": 4.6, "tbsp": 13.5, "ladle": 15.0}
DIET_LABELS = {"V": "vegan", "v": "vegetarian", "e": "eggetarian", "n": "non-vegetarian"}
ALLERGEN_CODES = {"g": "gluten", "d": "dairy", "e": "egg", "p": "peanut", "t": "tree nut", "s": "soy", "f": "fish", "c": "shellfish", "w": "sesame", "m": "mustard"}
SOURCE = "Bubbles reference estimate (typical values from IFCT 2017 / USDA FoodData Central; not a measurement)"
_JAIN_NO = ("onion", "garlic", "potato", "aloo", "carrot", "beet", "radish", "ginger", "mushroom", "sweet potato", "tikki", "samosa",
            "kachori", "vada pav", "pav bhaji", "bhel", "pani puri", "momos", "pizza", "burger", "sandwich", "pakora", "pakoda", "dum aloo",
            "gobi", "mixed", "korma", "kofta", "bhurji", "masala", "manchurian", "biryani", "pulao", "fried rice", "chowmein", "keema", "raita", "kachumber", "salad")


def _parse() -> dict[str, dict]:
    foods: dict[str, dict] = {}
    for line in _RAW.strip().splitlines():
        parts = line.split("|")
        if len(parts) != 12:
            raise ValueError(f"bad food row: {line!r}")
        name, aliases, cat, unit, grams, kcal, protein, carbs, fat, fibre, diet, allergens = parts
        grams_f = float(grams)
        row = {
            "name": name.strip(), "aliases": [a.strip() for a in aliases.split(",") if a.strip()], "category": cat, "unit": unit,
            "serving_g": grams_f, "serving": f"1 {unit}" + ("" if unit == "g" else f" (~{grams_f:g} g)"),
            "kcal": float(kcal), "protein_g": float(protein), "carbs_g": float(carbs), "fat_g": float(fat), "fibre_g": float(fibre),
            "diet": diet, "diet_label": DIET_LABELS[diet], "allergens": [ALLERGEN_CODES[c] for c in allergens],
            "micros": MICROS.get(name.strip(), {}),
            "jain_ok": diet in ("V", "v") and not any(w in name for w in _JAIN_NO),
            "source": SOURCE, "verified": False,
        }
        # sanity: macros must roughly explain the calories (catches typos); water/zero-calorie rows are exempt
        energy = row["protein_g"] * 4 + row["carbs_g"] * 4 + row["fat_g"] * 9
        if row["kcal"] > 20 and not 0.6 * row["kcal"] <= energy <= 1.45 * row["kcal"]:
            raise ValueError(f"{name}: macros ({energy:.0f} kcal) do not match {row['kcal']:.0f} kcal")
        foods[row["name"]] = row
    return foods


FOODS: dict[str, dict] = _parse()

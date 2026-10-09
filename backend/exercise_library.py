"""Curated exercise library. Not scraped: authored here. Each move lists equipment, level, impact and the conditions to avoid it for.

Row: id | name | category | pattern | equipment | level(1-3) | impact(0 low,1 medium,2 high) | avoid tags(,) | MET key | cue
Avoid tags: knee, lower_back, shoulder, wrist, neck, hypertension (heavy straining / overhead / head-down), pregnancy, postpartum,
osteoporosis (loaded spine flexion or twisting), balance (fall risk).
"""
from __future__ import annotations

_RAW = """
squat-chair|Sit-to-stand from a chair|strength|squat|chair|1|0||strength_light|Stand tall, sit back and down to the chair, push through your heels.
squat-body|Bodyweight squat|strength|squat|none|1|0||strength_light|Feet shoulder width, hips back, chest up, knees track over toes.
squat-goblet|Goblet squat|strength|squat|dumbbell|2|0||strength_light|Hold a weight at your chest, sit between your hips.
squat-wall|Wall sit|strength|squat|none|1|0|hypertension|strength_light|Back flat on the wall, thighs near parallel, breathe steadily.
squat-jump|Jump squat|strength|squat|none|3|2|knee,pregnancy,postpartum,osteoporosis,hypertension|hiit|Squat, then jump softly and land with bent knees.
squat-bar|Barbell back squat|strength|squat|gym|3|0|lower_back,hypertension,osteoporosis|strength_vigorous|Brace your core, controlled descent, drive up.
legpress|Leg press|strength|squat|gym|2|0|hypertension|strength_light|Feet shoulder width, lower slowly, do not lock the knees.
lunge-split|Split squat|strength|lunge|none|2|0|knee|strength_light|Long stance, lower straight down, front heel stays down.
lunge-reverse|Reverse lunge|strength|lunge|none|2|0|knee,balance|strength_light|Step back, lower both knees, push through the front heel.
stepup|Step-up|strength|lunge|step|2|0|knee,balance|strength_light|Step onto a sturdy step, stand tall, lower with control.
bridge-glute|Glute bridge|strength|hinge|none|1|0|pregnancy|strength_light|Lie on your back, press hips up, squeeze glutes, lower slowly.
bridge-single|Single-leg glute bridge|strength|hinge|none|2|0|pregnancy|strength_light|One foot planted, other leg extended, keep hips level.
hipthrust|Hip thrust|strength|hinge|bench|2|0|pregnancy|strength_light|Upper back on a bench, drive hips up, chin tucked.
rdl-db|Romanian deadlift (dumbbells)|strength|hinge|dumbbell|2|0|lower_back,osteoporosis|strength_light|Soft knees, hips back, flat back, feel the hamstrings stretch.
deadlift-bar|Barbell deadlift|strength|hinge|gym|3|0|lower_back,hypertension,osteoporosis|strength_vigorous|Brace, bar close to legs, push the floor away.
kb-swing|Kettlebell swing|strength|hinge|dumbbell|3|1|lower_back,hypertension,osteoporosis|strength_vigorous|Hinge, snap hips forward, arms are ropes.
hinge-band|Banded good morning|strength|hinge|band|1|0|lower_back|strength_light|Band under feet and over shoulders, hinge at the hips.
birddog|Bird dog|core|core|mat|1|0||strength_light|Opposite arm and leg reach long, keep hips square.
pushup-wall|Wall push-up|strength|push|none|1|0||strength_light|Hands on the wall, body in a line, bend elbows.
pushup-incline|Incline push-up|strength|push|bench|1|0|wrist|strength_light|Hands on a bench or counter, body straight.
pushup-knee|Knee push-up|strength|push|mat|1|0|wrist,pregnancy|strength_light|Knees down, hips in line with shoulders.
pushup|Push-up|strength|push|none|2|0|wrist,shoulder,pregnancy|strength_light|Body in a line, chest to the floor, elbows about 45 degrees.
pushup-pike|Pike push-up|strength|push|none|3|0|shoulder,wrist,hypertension,pregnancy|strength_vigorous|Hips high, lower the head between the hands.
press-band|Band chest press|strength|push|band|1|0||strength_light|Band around your back, press forward, slow return.
press-db|Dumbbell bench press|strength|push|dumbbell,bench|2|0|shoulder|strength_light|Shoulder blades back, lower to chest level, press.
press-ohp|Dumbbell overhead press|strength|push|dumbbell|2|0|shoulder,hypertension,neck|strength_light|Ribs down, press overhead without arching.
raise-lateral|Lateral raise|strength|push|dumbbell|1|0|shoulder|strength_light|Light weights, lift to shoulder height, slow.
dip-chair|Chair dip|strength|push|bench|2|0|shoulder,wrist|strength_light|Hands on a chair edge, lower elbows straight back.
bench-bar|Barbell bench press|strength|push|gym|3|0|shoulder,hypertension|strength_vigorous|Feet planted, controlled bar path, use a spotter.
row-band|Band row|strength|pull|band|1|0||strength_light|Pull elbows back, squeeze shoulder blades.
row-db|One-arm dumbbell row|strength|pull|dumbbell|1|0|lower_back|strength_light|Support one hand on a bench, pull to the hip.
row-inv|Inverted row|strength|pull|gym|2|0|shoulder|strength_light|Body straight under a bar, pull the chest up.
pulldown|Lat pulldown|strength|pull|gym|2|0|shoulder,neck|strength_light|Pull to upper chest, no swinging.
row-cable|Seated cable row|strength|pull|gym|2|0||strength_light|Tall posture, pull to the stomach.
pullapart|Band pull-apart|strength|pull|band|1|0||strength_light|Arms straight, pull the band to your chest.
pullup|Pull-up|strength|pull|gym|3|0|shoulder|strength_vigorous|Full hang, pull the chest to the bar.
curl-db|Biceps curl|strength|pull|dumbbell|1|0||strength_light|Elbows by your sides, slow lowering.
fly-rear|Rear delt fly|strength|pull|dumbbell|1|0|lower_back|strength_light|Hinge forward, lift arms out to the sides.
deadbug|Dead bug|core|core|mat|1|0|pregnancy|strength_light|Low back flat, opposite arm and leg lower slowly.
plank-knee|Knee plank|core|core|mat|1|0|wrist,postpartum|strength_light|Forearms down, knees down, straight line.
plank|Forearm plank|core|core|mat|2|0|wrist,hypertension,postpartum,pregnancy|strength_light|Elbows under shoulders, squeeze glutes, breathe.
plank-side|Side plank|core|core|mat|2|0|shoulder,postpartum,pregnancy|strength_light|Stack feet, lift hips, hold.
crunch|Crunch|core|core|mat|1|0|osteoporosis,neck,pregnancy,postpartum,lower_back|strength_light|Small curl up, hands light behind the head.
legraise|Lying leg raise|core|core|mat|2|0|lower_back,pregnancy,postpartum|strength_light|Low back pressed down, lower legs slowly.
pallof|Pallof press|core|core|band|1|0||strength_light|Press the band out and resist the twist.
twist-russian|Russian twist|core|core|mat|2|0|osteoporosis,lower_back,postpartum|strength_light|Lean back slightly, rotate the chest side to side.
climber|Mountain climber|core|core|none|2|1|wrist,pregnancy,hypertension,postpartum|hiit|Plank position, drive knees in quickly.
hollow|Hollow hold|core|core|mat|3|0|lower_back,pregnancy,postpartum,neck|strength_vigorous|Low back down, legs and shoulders slightly off the floor.
carry-farmer|Farmer carry|core|carry|dumbbell|1|0|hypertension|strength_light|Heavy-ish weights, stand tall, walk steadily.
walk-slow|Easy walk|cardio|cardio|none|1|0||walking_slow|Comfortable pace, you can chat easily.
walk-brisk|Brisk walk|cardio|cardio|none|1|0||walking_brisk|A pace where talking is possible but singing is not.
walk-hill|Incline or hill walk|cardio|cardio|none|2|0|knee|walking_uphill|Lean slightly forward, shorter steps.
walk-intervals|Walking intervals|cardio|cardio|none|1|0||walking_brisk|Alternate 2 minutes brisk with 1 minute easy.
march|Marching on the spot|cardio|cardio|none|1|0||walking_brisk|Lift knees to hip height, swing arms.
chair-cardio|Seated chair cardio|cardio|cardio|chair|1|0||walking_slow|Seated marching, arm reaches, gentle punches.
jog|Easy jog|cardio|cardio|none|2|1|knee,pregnancy,osteoporosis|jogging|Short strides, relaxed shoulders.
run|Run|cardio|cardio|none|3|2|knee,pregnancy,osteoporosis,hypertension|running|Build gradually, land softly.
cycle-easy|Easy cycling|cardio|cardio|bike|1|0||cycling_easy|Smooth pedalling, light resistance.
cycle-mod|Steady cycling|cardio|cardio|bike|2|0||cycling_moderate|Moderate resistance, steady cadence.
cycle-hiit|Cycling intervals|cardio|cardio|bike|3|0|hypertension|cycling_vigorous|30 seconds hard, 90 seconds easy.
swim-easy|Easy swimming|cardio|cardio|pool|1|0||swimming_easy|Relaxed strokes, breathe rhythmically.
swim-hard|Swim laps|cardio|cardio|pool|3|0|shoulder|swimming_vigorous|Steady laps with short rests.
elliptical|Elliptical|cardio|cardio|gym|1|0||elliptical|Upright posture, light grip.
rower|Rowing machine|cardio|cardio|gym|2|0|lower_back|rowing|Legs, then hips, then arms.
stairs|Stair climbing|cardio|cardio|stairs|2|1|knee|stairs|Whole foot on the step, hold the rail if needed.
dance|Dance workout|cardio|cardio|none|1|1|knee|dance|Any music you enjoy, keep moving.
zumba|Zumba-style class|cardio|cardio|none|2|1|knee|zumba|Follow a free video, keep it light on the joints.
jacks|Jumping jacks|cardio|cardio|none|2|2|knee,pregnancy,osteoporosis,hypertension|hiit|Land softly, keep a steady rhythm.
skip|Skipping rope|cardio|cardio|none|3|2|knee,pregnancy,osteoporosis|skipping|Small hops, wrists turn the rope.
highknees|High knees|cardio|cardio|none|3|2|knee,pregnancy,osteoporosis,hypertension|hiit|Drive knees up, stay light on the feet.
shadowbox|Shadow boxing|cardio|cardio|none|2|1||hiit|Light footwork, punch combinations.
hiit-circuit|Low-impact HIIT circuit|cardio|cardio|none|3|1|hypertension,pregnancy|hiit|40 seconds work, 20 seconds rest, low-impact versions.
surya|Surya namaskar (sun salutations)|cardio|cardio|mat|2|0|wrist,hypertension,pregnancy,osteoporosis|surya_namaskar|Move with your breath, slow and smooth.
mob-catcow|Cat-cow|mobility|mobility|mat|1|0|wrist|stretching|Round and arch the back with your breath.
mob-child|Child's pose|mobility|mobility|mat|1|0|knee,pregnancy|stretching|Sit back to the heels, arms long, breathe.
mob-hip|Hip flexor stretch|mobility|mobility|mat|1|0|knee|stretching|Half-kneeling, tuck the pelvis, lean forward gently.
mob-hamstring|Hamstring stretch|mobility|mobility|mat|1|0|lower_back|stretching|Leg straight, hinge from the hips, no bouncing.
mob-quad|Standing quad stretch|mobility|mobility|none|1|0|knee,balance|stretching|Heel to glute, knees together.
mob-shoulder|Shoulder circles|mobility|mobility|none|1|0||stretching|Big slow circles, both directions.
mob-neck|Gentle neck release|mobility|mobility|none|1|0|neck|stretching|Ear toward shoulder, no force.
mob-thoracic|Thoracic rotation|mobility|mobility|mat|1|0|osteoporosis|stretching|On all fours, hand behind head, rotate and open the chest.
mob-ankle|Ankle circles|mobility|mobility|none|1|0||stretching|Slow circles, both ways.
mob-world|World's greatest stretch|mobility|mobility|mat|2|0|knee,osteoporosis|stretching|Lunge, rotate the chest up, switch sides.
mob-pigeon|Pigeon pose|mobility|mobility|mat|2|0|knee|yoga|Front shin forward, hips level, breathe.
mob-bridge|Supported bridge|mobility|mobility|mat|1|0|pregnancy|yoga|Support under the hips, rest, breathe.
mob-cobra|Cobra pose|mobility|mobility|mat|1|0|pregnancy,lower_back|yoga|Chest lifts gently, shoulders away from the ears.
mob-legsup|Legs up the wall|mobility|mobility|mat|1|0|pregnancy|yoga|Rest the legs on a wall, breathe slowly.
mob-forwardfold|Seated forward fold|mobility|mobility|mat|1|0|osteoporosis,lower_back|stretching|Long spine, fold from the hips, no pulling.
mob-twist|Seated spinal twist|mobility|mobility|mat|1|0|osteoporosis|stretching|Tall spine, gentle rotation.
mob-downdog|Downward dog|mobility|mobility|mat|2|0|wrist,hypertension,pregnancy,shoulder|yoga|Hips high, press the floor away, bend knees if tight.
yoga-warrior|Warrior II|mobility|mobility|mat|1|0|knee|yoga|Front knee over ankle, arms reach, steady breath.
yoga-tree|Tree pose|mobility|balance|none|1|0|balance|yoga|Foot to calf or thigh, never the knee, eyes on one spot.
balance-leg|Single-leg stand|mobility|balance|none|1|0|balance|stretching|Hold a chair if needed, stand tall.
balance-heel|Heel-to-toe walk|mobility|balance|none|1|0|balance|walking_slow|Walk in a straight line, foot in front of foot.
breath-box|Box breathing|mobility|mobility|none|1|0||stretching|In 4, hold 4, out 4, hold 4.
breath-pranayama|Slow nostril breathing|mobility|mobility|none|1|0||stretching|Slow, comfortable breaths. Stop if lightheaded.
breath-diaphragm|Diaphragmatic belly breathing|mobility|mobility|none|1|0||stretching|Hand on belly, breathe low and slow, longer out-breath.
squat-sumo|Sumo squat|strength|squat|none|1|0|knee|strength_light|Wide stance, toes out, sit down between the feet.
squat-pause|Pause squat|strength|squat|none|2|0|knee|strength_light|Hold two seconds at the bottom, drive up smoothly.
squat-band|Banded squat|strength|squat|band|1|0|knee|strength_light|Band above the knees, push the knees out as you sit.
squat-split-bulg|Bulgarian split squat|strength|lunge|bench|3|0|knee,balance|strength_vigorous|Back foot on a bench, lower straight down.
lunge-walking|Walking lunge|strength|lunge|none|2|0|knee,balance|strength_light|Long steps, upright chest, back knee near the floor.
lunge-lateral|Side lunge|strength|lunge|none|2|0|knee|strength_light|Step wide, sit back into one hip, other leg straight.
calf-raise|Calf raise|strength|lunge|none|1|0||strength_light|Rise onto the toes, slow lower. Hold a wall if needed.
hipabd-band|Banded side-lying leg raise|strength|hinge|band|1|0||strength_light|On your side, lift the top leg slowly, no rocking.
clam|Clamshell|strength|hinge|band|1|0||strength_light|On your side, knees bent, open the top knee, keep the feet together.
donkey|Donkey kick|strength|hinge|mat|1|0|wrist,pregnancy|strength_light|On all fours, press one heel to the ceiling.
rdl-single|Single-leg Romanian deadlift|strength|hinge|dumbbell|3|0|lower_back,balance|strength_light|Hinge on one leg, flat back, hips square.
swing-band|Banded pull-through|strength|hinge|band|2|0|lower_back|strength_light|Band anchored behind, hinge and snap the hips forward.
pushup-decline|Decline push-up|strength|push|bench|3|0|shoulder,wrist,pregnancy|strength_vigorous|Feet on a bench, body straight, lower the chest.
pushup-diamond|Close-grip push-up|strength|push|none|3|0|wrist,shoulder,pregnancy|strength_vigorous|Hands close under the chest, elbows tucked.
press-floor|Dumbbell floor press|strength|push|dumbbell|1|0|pregnancy|strength_light|Lie on the floor, elbows rest between reps.
triceps-ext|Overhead triceps extension|strength|push|dumbbell|1|0|shoulder,neck|strength_light|Elbows by the ears, lower behind the head with control.
triceps-kick|Triceps kickback|strength|push|dumbbell|1|0|lower_back|strength_light|Hinge forward, extend the elbow straight back.
press-arnold|Arnold press|strength|push|dumbbell|2|0|shoulder,hypertension,neck|strength_light|Rotate palms from facing you to facing forward as you press.
row-bent|Bent-over row|strength|pull|dumbbell|2|0|lower_back|strength_light|Hinge, flat back, pull the weights to the ribs.
row-towel|Towel door row|strength|pull|none|1|0||strength_light|Hold a towel around a sturdy door handle, lean back and row.
curl-hammer|Hammer curl|strength|pull|dumbbell|1|0||strength_light|Palms facing each other, elbows still.
curl-band|Banded curl|strength|pull|band|1|0||strength_light|Stand on the band, curl up slowly.
shrug|Shoulder shrug|strength|pull|dumbbell|1|0|neck|strength_light|Lift the shoulders straight up, pause, lower.
pullover|Dumbbell pullover|strength|pull|dumbbell,bench|2|0|shoulder|strength_light|Arc the weight over the head with soft elbows.
lat-band|Banded lat pulldown|strength|pull|band|1|0||strength_light|Band anchored overhead, pull the elbows down to the ribs.
plank-shoulder|Plank shoulder tap|core|core|mat|2|0|wrist,shoulder,pregnancy,postpartum|strength_light|Wide feet, tap the opposite shoulder without rocking.
heel-touch|Heel taps|core|core|mat|1|0|neck,pregnancy|strength_light|Lie on your back, reach side to side to touch the heels.
bicycle|Bicycle crunch|core|core|mat|2|0|osteoporosis,neck,pregnancy,postpartum|strength_light|Slow cycling legs, elbow toward the opposite knee.
reverse-crunch|Reverse crunch|core|core|mat|2|0|lower_back,pregnancy,postpartum|strength_light|Curl the hips up using the lower abs, not momentum.
superman|Superman hold|core|core|mat|1|0|pregnancy,lower_back|strength_light|Lie face down, lift arms and legs a little, breathe.
core-stir|Stability ball stir|core|core|mat|3|0|postpartum,pregnancy|strength_vigorous|Forearms on a ball, draw slow circles.
woodchop-band|Banded wood chop|core|core|band|2|0|lower_back,osteoporosis|strength_light|Pivot the feet, rotate through the trunk, arms straight.
suitcase|Suitcase carry|core|carry|dumbbell|1|0||strength_light|Weight in one hand, stand tall, walk without leaning.
overhead-carry|Overhead carry|core|carry|dumbbell|3|0|shoulder,hypertension,neck|strength_vigorous|One arm overhead, ribs down, steady walk.
cycle-spin|Indoor cycling class|cardio|cardio|bike|2|0||cycling_moderate|Follow an easy video, adjust the resistance to feel moderate.
walk-nordic|Pole walking|cardio|cardio|none|1|0||walking_brisk|Use walking poles, let the arms drive the pace.
walk-treadmill|Treadmill incline walk|cardio|cardio|gym|2|0|knee|walking_uphill|Moderate incline, hands free, steady pace.
swim-aqua|Water walking or aqua aerobics|cardio|cardio|pool|1|0||swimming_easy|Chest-deep water, easy movements. Very kind to the joints.
badminton|Badminton|cardio|cardio|none|1|1|knee|badminton|Friendly rallies. Warm up first.
football|Football or kick-about|cardio|cardio|none|2|2|knee,pregnancy|football|Play at an easy pace with warm-up.
cricket-nets|Cricket nets or catch|cardio|cardio|none|1|1||cricket|Light practice, stay hydrated.
basketball|Basketball shooting|cardio|cardio|none|2|1|knee|basketball|Shooting drills and light play.
tennis|Tennis rallies|cardio|cardio|none|2|1|knee|tennis|Easy rallies, build gradually.
stairs-home|Stair laps at home|cardio|cardio|stairs|1|1|knee|stairs|Two to four easy laps, hold the rail.
skater|Low-impact skater steps|cardio|cardio|none|1|0|knee,balance|dance|Side to side glides without jumping.
boxing-bag|Bag work|cardio|cardio|none|2|1|wrist,shoulder|hiit|Light combinations with rest rounds.
rope-ladder|Agility ladder or line drills|cardio|cardio|none|2|1|knee,balance|hiit|Quick feet through a taped ladder on the floor.
yoga-flow|Gentle vinyasa flow|mobility|mobility|mat|2|0|wrist,pregnancy,hypertension|yoga|Link simple poses with the breath, never force a stretch.
yoga-thread|Thread the needle|mobility|mobility|mat|1|0|shoulder|yoga|On all fours, slide one arm under the other, rest the shoulder.
yoga-chair|Chair yoga sequence|mobility|mobility|chair|1|0||yoga|Seated poses for the spine, shoulders and hips.
yoga-lizard|Low lunge with rotation|mobility|mobility|mat|2|0|knee|yoga|Lunge, hand down, rotate the chest open.
yoga-happy|Happy baby|mobility|mobility|mat|1|0|pregnancy|yoga|On your back, hold the feet, rock gently.
yoga-garland|Garland pose (malasana)|mobility|mobility|mat|2|0|knee|yoga|Deep squat with support under the heels if tight.
yoga-sidebend|Seated side bend|mobility|mobility|mat|1|0||stretching|Reach one arm overhead and lean, long through the side.
stretch-chest|Doorway chest stretch|mobility|mobility|none|1|0|shoulder|stretching|Forearms on a doorframe, step through gently.
stretch-calf|Wall calf stretch|mobility|mobility|none|1|0||stretching|Heel down, lean to the wall, feel the calf lengthen.
stretch-glute|Figure-four stretch|mobility|mobility|mat|1|0|knee|stretching|On your back, ankle over the opposite knee, draw in.
stretch-lat|Kneeling lat stretch|mobility|mobility|mat|1|0|shoulder|stretching|Hands on a bench or couch, sit back, chest toward the floor.
stretch-wrist|Wrist and forearm stretch|mobility|mobility|none|1|0||stretching|Palm out, gently draw the fingers back.
foam-roll|Foam or ball self-massage|mobility|mobility|mat|1|0||stretching|Roll slowly over big muscles, avoid joints and sharp pain.
balance-clock|Single-leg clock reach|mobility|balance|none|2|0|balance|stretching|Stand on one leg and reach the other foot to clock positions.
balance-tandem|Tandem stance|mobility|balance|none|1|0|balance|stretching|One foot directly in front of the other, hold a chair nearby.
walk-mindful|Mindful walking|mobility|mobility|none|1|0||walking_slow|Slow walk, notice the feet and breath. Good on a stressful day.
"""

LIB: dict[str, dict] = {}
for _line in _RAW.strip().splitlines():
    _p = _line.split("|")
    assert len(_p) == 10, _line
    _id, _name, _cat, _pat, _eq, _lvl, _imp, _avoid, _met, _cue = _p
    LIB[_id] = {"id": _id, "name": _name, "category": _cat, "pattern": _pat, "equipment": [e for e in _eq.split(",") if e], "level": int(_lvl),
                "impact": int(_imp), "avoid": [a for a in _avoid.split(",") if a], "met": _met, "cue": _cue}

EQUIPMENT_GROUPS = {"none": {"none", "mat", "chair", "step"}, "home": {"none", "mat", "chair", "step", "band", "dumbbell", "bench", "stairs"},
                    "gym": {"none", "mat", "chair", "step", "band", "dumbbell", "bench", "stairs", "gym", "bike"}, "pool": {"pool"}}
# a "mat" is assumed to be a towel/yoga mat; a chair a sturdy dining chair; "step" a stair or sturdy box

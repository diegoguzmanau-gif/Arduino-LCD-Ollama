"""
Compare Ollama models on the 100 exhibition questions.

Run it from the same folder as ollama_lcd.py:

    python model_test.py qwen3:1.7b gemma2:2b gemma3:1b

Add --quick to run only every 3rd question (about 34) for a fast first look.
Pull each model first, for example:  ollama pull gemma2:2b
"""

import re
import sys
import time

import ollama_lcd as ai

# (question, accepted answers). An answer counts as correct if it contains any of them.
QUESTIONS = [
    # Animals
    ("What is the biggest animal on earth?", ["blue whale"]),
    ("What is the fastest land animal?", ["cheetah"]),
    ("How many legs does a spider have?", ["8", "eight"]),
    ("What do pandas eat?", ["bamboo"]),
    ("What is a baby dog called?", ["puppy"]),
    ("What is the tallest animal?", ["giraffe"]),
    ("Which bird cannot fly and lives in Antarctica?", ["penguin"]),
    ("What sound does a cow make?", ["moo"]),
    ("How many legs does an insect have?", ["6", "six"]),
    ("What animal is called the king of the jungle?", ["lion"]),
    # Geography
    ("What is the capital of France?", ["paris"]),
    ("What is the capital of Australia?", ["canberra"]),
    ("What is the largest ocean?", ["pacific"]),
    ("What is the biggest country by area?", ["russia"]),
    ("What continent is Egypt in?", ["africa"]),
    ("What is the capital of Japan?", ["tokyo"]),
    ("What is the tallest mountain on earth?", ["everest"]),
    ("How many continents are there?", ["7", "seven"]),
    ("What is the capital of Italy?", ["rome"]),
    ("What is the largest continent?", ["asia"]),
    # Space
    ("What is the closest star to earth?", ["sun"]),
    ("What is the biggest planet?", ["jupiter"]),
    ("Which planet is called the red planet?", ["mars"]),
    ("How many planets are in our solar system?", ["8", "eight"]),
    ("What orbits the earth?", ["moon"]),
    ("What is the hottest planet?", ["venus"]),
    ("Which planet has rings?", ["saturn"]),
    ("Who was the first person on the moon?", ["armstrong"]),
    ("What galaxy do we live in?", ["milky way"]),
    ("What is the smallest planet?", ["mercury"]),
    # Science
    ("What gas do humans breathe in?", ["oxygen"]),
    ("What gas do plants take in?", ["carbon dioxide", "co2"]),
    ("What is water made of?", ["hydrogen"]),
    ("At what temperature does water boil in Celsius?", ["100"]),
    ("At what temperature does water freeze in Celsius?", ["0", "zero"]),
    ("What force pulls things to the ground?", ["gravity"]),
    ("What is the hardest natural material?", ["diamond"]),
    ("What is the chemical symbol for gold?", ["au"]),
    ("What is the center of an atom called?", ["nucleus"]),
    ("What is the largest organ in the human body?", ["skin"]),
    # Human body
    ("How many teeth do adults normally have?", ["32"]),
    ("How many hearts does a human have?", ["1", "one"]),
    ("What organ pumps blood?", ["heart"]),
    ("What organ do we use to see?", ["eye", "eyes"]),
    ("How many senses do humans have?", ["5", "five"]),
    ("What organ do we use to breathe?", ["lung", "lungs"]),
    ("How many bones are in an adult human body?", ["206"]),
    ("What color is blood?", ["red"]),
    ("How many eyes do humans have?", ["2", "two"]),
    ("What organ helps us hear?", ["ear", "ears"]),
    # Math
    ("What is 2 plus 2?", ["4", "four"]),
    ("What is 10 times 10?", ["100", "hundred"]),
    ("What is 9 minus 4?", ["5", "five"]),
    ("What is 12 divided by 3?", ["4", "four"]),
    ("What is 7 times 8?", ["56"]),
    ("What is 15 plus 27?", ["42"]),
    ("What is half of 100?", ["50", "fifty"]),
    ("How many sides does a triangle have?", ["3", "three"]),
    ("How many sides does a hexagon have?", ["6", "six"]),
    ("What is the square root of 81?", ["9", "nine"]),
    # Time and calendar
    ("How many days are in a week?", ["7", "seven"]),
    ("How many months are in a year?", ["12", "twelve"]),
    ("How many hours are in a day?", ["24"]),
    ("How many minutes are in an hour?", ["60", "sixty"]),
    ("What day comes after Monday?", ["tuesday"]),
    ("What month comes after March?", ["april"]),
    ("How many seconds are in a minute?", ["60", "sixty"]),
    ("How many days are in a leap year?", ["366"]),
    ("What is the first month of the year?", ["january"]),
    ("How many days are in February in a normal year?", ["28"]),
    # Letters and words
    ("How many r are in strawberry?", ["3", "three"]),
    ("How many letters are in the word cat?", ["3", "three"]),
    ("How do you spell dog?", ["d o g", "d-o-g", "d, o, g"]),
    ("What is the first letter of the alphabet?", ["a"]),
    ("How many letters are in the alphabet?", ["26", "twenty-six"]),
    ("What is the last letter of the alphabet?", ["z"]),
    ("How many vowels are in the alphabet?", ["5", "five"]),
    ("What is the opposite of hot?", ["cold"]),
    ("What is the opposite of up?", ["down"]),
    ("What rhymes with cat?", ["hat", "bat", "mat", "rat", "sat", "fat", "pat", "chat", "flat"]),
    # Colors and everyday things
    ("What color do you get mixing red and blue?", ["purple", "violet"]),
    ("What color do you get mixing blue and yellow?", ["green"]),
    ("What color are bananas?", ["yellow"]),
    ("What color is grass?", ["green"]),
    ("How many colors are in a rainbow?", ["7", "seven"]),
    ("What color is a stop sign?", ["red"]),
    ("What color are carrots?", ["orange"]),
    ("What do you call a baby cat?", ["kitten"]),
    ("What do bees make?", ["honey"]),
    ("What tool do we use to tell the time?", ["clock", "watch"]),
    # General knowledge
    ("What fruit keeps the doctor away?", ["apple"]),
    ("Who painted the Mona Lisa?", ["da vinci", "leonardo"]),
    ("Who wrote Romeo and Juliet?", ["shakespeare"]),
    ("What language is spoken in Brazil?", ["portuguese"]),
    ("What currency does Japan use?", ["yen"]),
    ("How many players are on a soccer team?", ["11", "eleven"]),
    ("What sport uses a hoop and a ball?", ["basketball"]),
    ("What does a computer mouse do?", ["cursor", "pointer", "move", "moves"]),
    ("What is the main ingredient in bread?", ["flour"]),
    ("What is the opposite of day?", ["night"]),
]


def is_correct(answer, accepted):
    a = answer.lower()
    return any(re.search(rf"(?<!\w){re.escape(k)}(?!\w)", a) for k in accepted)


def run_model(name, questions):
    ai.OLLAMA_MODEL = name
    print(f"\n=== {name} ===")
    print("Loading model (the first call is slow and is not counted)...")
    ai.ask_ollama("What color is the sky?")

    correct = 0
    times = []
    misses = []

    for i, (question, accepted) in enumerate(questions, 1):
        start = time.time()
        try:
            answer = ai.ask_ollama(question)
        except Exception as e:
            answer = f"ERROR: {e}"
        elapsed = time.time() - start
        times.append(elapsed)

        ok = is_correct(answer, accepted)
        if ok:
            correct += 1
        else:
            misses.append((question, answer))

        print(f"{i:3} {'OK  ' if ok else 'MISS'} {elapsed:5.1f}s  {question} -> {answer}")

    # Unload so the next model has the RAM to itself
    try:
        ai.client.chat(model=name, messages=[], keep_alive=0)
    except Exception:
        pass

    avg = sum(times) / len(times)
    print(f"\n{name}: {correct}/{len(questions)} correct, "
          f"{avg:.1f}s average, {max(times):.1f}s slowest")
    return name, correct, len(questions), avg, max(times)


def main():
    args = sys.argv[1:]
    quick = "--quick" in args
    models = [a for a in args if not a.startswith("--")]

    if not models:
        models = [ai.OLLAMA_MODEL]

    questions = QUESTIONS[::3] if quick else QUESTIONS

    results = [run_model(m, questions) for m in models]

    print("\n=== SUMMARY ===")
    for name, correct, total, avg, slowest in results:
        print(f"{name:20} {correct:3}/{total}   avg {avg:5.1f}s   slowest {slowest:5.1f}s")

    print("\nPick the model with the best score that stays under ~10s average.")
    print("Anything over 60s on a single question will trip the Arduino timeout.")


if __name__ == "__main__":
    main()

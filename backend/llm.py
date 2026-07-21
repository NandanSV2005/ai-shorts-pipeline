import os
from backend.config import LLM_PROVIDER, GEMINI_API_KEY, OPENAI_API_KEY, MOCK_PIPELINE

def clean_json_response(text: str) -> str:
    """Strips markdown code block backticks if present in LLM response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text

def generate_text(prompt: str, system_instruction: str | None = None) -> str:
    """
    Unified entry point for text generation. Swaps between Gemini and OpenAI
    based on LLM_PROVIDER in config. Falls back to mock data if MOCK_PIPELINE is True.
    """
    if MOCK_PIPELINE:
        print("[LLM Interface] MOCK_PIPELINE is enabled. Generating simulated response...")
        prompt_lower = prompt.lower()
        
        # Helper to get current run date directory from CLI args
        import sys
        from datetime import datetime
        def get_active_date() -> str:
            date_str = datetime.now().strftime("%Y-%m-%d")
            for idx, arg in enumerate(sys.argv):
                if arg == "--date" and idx + 1 < len(sys.argv):
                    date_str = sys.argv[idx + 1]
                    break
            return date_str

        # Helper to get parts count from metadata
        def get_parts_count() -> int:
            try:
                from backend.config import OUTPUTS_DIR
                import json
                date_str = get_active_date()
                metadata_file = OUTPUTS_DIR / date_str / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        return json.load(f).get("parts", 1)
            except Exception:
                pass
            return 1

        # Pool of distinct topics for mock series episodes
        MOCK_TOPICS = [
            {
                "title": "AITA for Refusing to Give Up My Seat to a Pregnant Woman?",
                "concept": "A narrator refuses to yield their train seat to a pregnant woman because they had a long day at a grueling physical job, resulting in a public scene and family controversy.",
                "keywords": ["subway train drama", "pregnancy debate", "aita train seat", "family drama"],
                "visual_style": "bold white text, dramatic shadows, red accent accents"
            },
            {
                "title": "AITA for Canceling My Sister's Wedding Caterer After She Insulted My Wife?",
                "concept": "The narrator pays for their sister's wedding caterer, but cancels the booking after the sister makes a series of cruel remarks about the narrator's wife, causing a huge wedding fallout.",
                "keywords": ["wedding drama", "caterer cancellation", "aita wedding conflict", "family feud"],
                "visual_style": "wedding aesthetic, clean elegant titles, red highlight alerts"
            },
            {
                "title": "AITA for Exposing My Fiancé's Secret Family at Our Rehearsal Dinner?",
                "concept": "The narrator discovers their fiancé has been living a double life with a secret family, and reveals the proof at their rehearsal dinner in front of all their friends and family.",
                "keywords": ["wedding rehearsal dinner exposure", "double life reveal", "aita wedding drama", "fiancé betrayal"],
                "visual_style": "rehearsal dinner setting, dark high-contrast text, yellow warn boxes"
            },
            {
                "title": "AITA for Firing My Mother-in-Law from My Business?",
                "concept": "The narrator hires their mother-in-law to help with their business, but has to fire her after she repeatedly undermines the narrator's authority and leaks trade secrets to competitors.",
                "keywords": ["family business conflict", "mother in law drama", "aita firing employee", "workplace family conflict"],
                "visual_style": "modern office backdrop, sleek bold fonts, orange outline alerts"
            },
            {
                "title": "AITA for Telling My Boss to Do His Own Job and Getting Him Fired?",
                "concept": "A narrator refuses to cover for their lazy manager, telling them to do their own job, and presents a detailed report of the manager's incompetence to HR, leading to the manager's immediate firing.",
                "keywords": ["workplace revenge", "hr investigation", "aita bad manager", "corporate compliance drama"],
                "visual_style": "corporate cubicle environment, high-contrast dark mode, green badge borders"
            }
        ]

        # Try to extract the title from the prompt
        title = None
        for line in prompt.splitlines():
            if line.startswith("Topic Title:"):
                title = line.replace("Topic Title:", "").strip()
                break
        if not title:
            try:
                from backend.config import OUTPUTS_DIR
                date_str = get_active_date()
                topic_file = OUTPUTS_DIR / date_str / "topic.json"
                if topic_file.exists():
                    import json
                    with open(topic_file, "r", encoding="utf-8") as f:
                        title = json.load(f).get("title")
            except Exception:
                pass

        # Step 01: Topic Generator
        if "generate a single new video topic" in prompt_lower:
            date_str = get_active_date()
            series = None
            episode = None
            try:
                from backend.config import OUTPUTS_DIR
                import json
                metadata_file = OUTPUTS_DIR / date_str / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        series = meta.get("series")
                        episode = meta.get("episode")
            except Exception:
                pass
                
            hash_key = date_str
            if series:
                hash_key += f"_{series}"
            if episode is not None:
                hash_key += f"_ep{episode}"
                
            if episode is not None:
                topic_index = (episode - 1) % len(MOCK_TOPICS)
            else:
                import hashlib
                h = int(hashlib.md5(hash_key.encode()).hexdigest(), 16)
                topic_index = h % len(MOCK_TOPICS)
                
            selected_topic = MOCK_TOPICS[topic_index]
            import json
            return json.dumps(selected_topic, indent=2, ensure_ascii=False)
        # Step 04: Story Consistency Checker
        elif "compare the following script against the research report" in prompt_lower or "compare the following script against the story outline" in prompt_lower or "consistency" in prompt_lower or "fact-check" in prompt_lower:
            return f"""[
              {{
                "claim": "The narrator is a bricklayer who was physically exhausted after a 12-hour shift.",
                "status": "VERIFIED",
                "explanation": "Consistent with character profile and timeline in the story outline."
              }},
              {{
                "claim": "The narrator's partner supported them from the beginning.",
                "status": "FLAGGED",
                "explanation": "Contradiction: the script states the partner was horrified, told them to apologize, and stopped returning texts."
              }}
            ]"""
        # Step 03: Script Writer
        elif "draft a complete youtube script" in prompt_lower or "script to revise" in prompt_lower or "first-person" in prompt_lower:
            parts_count = get_parts_count()
            display_title = title or "AITA for Refusing to Give Up My Seat to a Pregnant Woman?"
            if "seat" in display_title.lower():
                script_text = f"""[HOOK]
[SCENE: Gameplay showing fast parkour movements]
AITA for refusing to give up my seat to a pregnant woman? So this happened yesterday on my commute home, and now my family is calling me a monster.

[BODY]
[SCENE: Fast-paced subway train layout footage]
I work as a commercial bricklayer. It is physical labor, and yesterday I finished a twelve-hour shift. My back was throbbing, and my feet were blistered. When I boarded the train, I managed to grab one of the few open seats. I closed my eyes, just wanting to rest.

[SCENE: Crowd of people talking and gesturing]
Three stops later, a woman who was visibly pregnant boarded the train. She walked straight over to me, stood right in front of my face, and cleared her throat loudly. She said, 'Excuse me, I need that seat.'

[SCENE: Close-up of narrator refusing]
I opened my eyes, looked around, and saw other young, healthy-looking people in seats. I politely said, 'I'm sorry, but I just finished a twelve-hour shift of heavy physical labor and I can barely stand.'

[SCENE: Angry passengers shouting and recording]
I refused to budge. Another passenger pulled out a phone and started filming me, telling me to get up or they'd put the video online.
[SPLIT POINT]
[SCENE: Viral video screenshot overlay]
By the time I got home, the video was already trending on social media. My partner saw it and was horrified. They told me I brought shame on them and that I should pack my things if I didn't publicly apologize to the woman.

[SCENE: Revealing train footage angles]
But here is the twist: a commuter who was sitting next to me posted another angle. It clearly showed that the pregnant woman had walked past three empty priority seats right behind her just to target me. Public opinion has split, but my partner still hasn't returned my texts.

[CTA/OUTRO]
[SCENE: Channel logo and subscribe button animation]
So, AITA? Let me know what you think in the comments, and don't forget to subscribe for more Reddit confessions.
"""
            else:
                script_text = f"""[HOOK]
[SCENE: Gameplay showing fast parkour movements]
Here is the story about {display_title}. So this happened recently, and it completely ruined my week.

[BODY]
[SCENE: High-intensity gameplay clip]
It all started when I was dealing with a very difficult situation. Everyone thought I was in the wrong, but they didn't know the full story.

[SCENE: Subway surfers gameplay transition]
I tried to explain my side, but nobody wanted to listen. Things escalated very quickly, and before I knew it, it was a total disaster.
[SPLIT POINT]
[SCENE: Intense gameplay speedrun]
That's when the big twist happened. I discovered something that changed everything, and I had to make a choice.

[SCENE: Gameplay completion showing high score]
Ultimately, I stood my ground, and the truth came out. It was a tough lesson, but I don't regret it.

[CTA/OUTRO]
[SCENE: Channel logo and subscribe button animation]
So, what do you think? Was I the jerk? Tell me in the comments and subscribe for more stories!
"""
            if parts_count == 1:
                script_text = script_text.replace("[SPLIT POINT]\n", "").replace("[SPLIT POINT]", "")
            return script_text

        # Step 02: Story Outline / Research Agent
        elif "generate a detailed research report" in prompt_lower or "outline a detailed fictional story" in prompt_lower:
            display_title = title or "AITA for Refusing to Give Up My Seat to a Pregnant Woman?"
            return f"""# Story Outline: {display_title}
            
## Character Profiles
- Narrator: 28-year-old construction worker, exhausted from a 12-hour shift.
- Pregnant Woman: Around 8 months pregnant, entered the train demanding a seat.
- Passengers: Bystanders who filmed the confrontation and made comments.

## Story Beats & Structure
- Setup: Narrator boards a crowded train after a grueling day and finds a seat.
- Conflict: A pregnant woman boards, looks at the narrator, and loudly demands they stand up.
- Escalation: Narrator refuses, citing physical exhaustion. A passenger records the scene, calling the narrator selfish.
- Cliffhanger: The video goes viral online, and the narrator's partner says they should apologize or move out. [SPLIT POINT]
- Twist/Resolution: The narrator holds their ground. It is revealed that the woman had other seating options nearby, and public opinion shifts back.

## Emotional Arc & Pacing
- Starts with exhaustion, escalates to high tension and public shame, and resolves with validation. Keep dialogue sharp.
"""

        # Step 10: SEO Generator
        elif "seo" in prompt_lower or "tags" in prompt_lower:
            parts_count = get_parts_count()
            display_title = title or "AITA for Refusing to Give Up My Seat to a Pregnant Woman?"
            if parts_count == 2:
                return f"""{{
                  "title": "{display_title} | Shorts",
                  "part1": {{
                    "title": "{display_title} - Part 1",
                    "description": "Was I wrong for holding my ground on the commute? This is a fictional story for entertainment purposes. #redditstories #aita #shorts",
                    "tags": ["redditstories", "aita", "relationshipdrama", "shorts"]
                  }},
                  "part2": {{
                    "title": "{display_title} - Part 2",
                    "description": "Here is Part 2 of this crazy story. This is a fictional story for entertainment purposes. #redditstories #aita #shorts",
                    "tags": ["redditstories", "aita", "relationshipdrama", "shorts"]
                  }}
                }}"""
            else:
                return f"""{{
                  "title": "{display_title} | Shorts",
                  "description": "Was I wrong for holding my ground on the commute? This is a fictional story for entertainment purposes. #redditstories #aita #shorts",
                  "tags": ["redditstories", "aita", "relationshipdrama", "shorts"]
                }}"""
        
        else:
            return "This is a generic mock response from the LLM pipeline."

    # Active LLM Logic

    if LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in the environment or .env file.")
        
        import google.genai as genai
        from google.genai import types
        import time
        
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        config = types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.95,
            max_output_tokens=8192,
            system_instruction=system_instruction
        )
        
        max_retries = 3
        backoff_sec = 2.0
        response = None
        for attempt in range(max_retries + 1):
            try:
                response = client.models.generate_content(
                    model="gemini-3.5-flash",
                    contents=prompt,
                    config=config
                )
                break
            except Exception as e:
                err_str = str(e).lower()
                if ("429" in err_str or "resource_exhausted" in err_str or "quota" in err_str) and attempt < max_retries:
                    print(f"[LLM Interface] Gemini rate limit hit (429/quota). Retrying in {backoff_sec} seconds (Attempt {attempt+1}/{max_retries})...")
                    time.sleep(backoff_sec)
                    backoff_sec *= 2
                else:
                    raise e
        
        if not response or not response.text:
            raise RuntimeError("Gemini returned an empty response.")
        return response.text

    elif LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in the environment or .env file.")
        
        from openai import OpenAI
        import time
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        max_retries = 3
        backoff_sec = 2.0
        response = None
        for attempt in range(max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.7,
                )
                break
            except Exception as e:
                err_str = str(e).lower()
                if ("429" in err_str or "rate" in err_str or "quota" in err_str) and attempt < max_retries:
                    print(f"[LLM Interface] OpenAI rate limit hit (429/quota). Retrying in {backoff_sec} seconds (Attempt {attempt+1}/{max_retries})...")
                    time.sleep(backoff_sec)
                    backoff_sec *= 2
                else:
                    raise e
                    
        content = response.choices[0].message.content  # type: ignore
        if not content:
            raise RuntimeError("OpenAI returned an empty response.")
        return content

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER}. Supported providers are 'gemini' and 'openai'.")

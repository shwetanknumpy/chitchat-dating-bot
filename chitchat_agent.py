import urllib.request
import json
import websocket
import ssl
import sys
import time
import re
import functools
import os

# Force all print statements to flush immediately for real-time IDE logging
print = functools.partial(print, flush=True)

LEARNED_PATTERNS_FILE = "/Users/shwetank/.gemini/antigravity-ide/scratch/learned_patterns.json"

def load_learned_patterns():
    if os.path.exists(LEARNED_PATTERNS_FILE):
        try:
            with open(LEARNED_PATTERNS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"names": [], "roots": []}

def save_learned_patterns(patterns):
    try:
        with open(LEARNED_PATTERNS_FILE, "w") as f:
            json.dump(patterns, f, indent=2)
    except Exception as e:
        print(f"Error saving learned patterns: {e}")

def learn_male_pattern(partner):
    patterns = load_learned_patterns()
    partner_lower = partner.lower().strip()
    
    modified = False
    if partner_lower not in patterns["names"]:
        patterns["names"].append(partner_lower)
        modified = True
        
    words = re.findall(r'\b\w+\b', partner_lower)
    ignored_words = {"user", "guest", "stranger", "the", "and", "new", "chat"}
    for word in words:
        if len(word) >= 3 and not word.isdigit() and word not in ignored_words:
            if word not in patterns["roots"]:
                patterns["roots"].append(word)
                modified = True
                
    if modified:
        save_learned_patterns(patterns)
        learned_words = [w for w in words if len(w) >= 3 and not w.isdigit() and w not in ignored_words]
        print(f"[Bot] 🧠 Persistent self-learning: Exact name '{partner_lower}' and roots {learned_words} logged as male patterns!")

def get_chitchat_tab():
    try:
        response = urllib.request.urlopen("http://127.0.0.1:9222/json")
        pages = json.loads(response.read().decode())
        for page in pages:
            if "chitchat" in page.get("url", "").lower() or "chitchat" in page.get("title", "").lower():
                return page.get("webSocketDebuggerUrl")
    except Exception as e:
        print(f"Error fetching Chrome tabs: {e}", file=sys.stderr)
    return None

def execute_js(ws_url, expression):
    try:
        ws = websocket.create_connection(ws_url, sslopt={"cert_reqs": ssl.CERT_NONE}, suppress_origin=True, timeout=5)
        payload = {
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "returnByValue": True
            }
        }
        ws.send(json.dumps(payload))
        result = ws.recv()
        ws.close()
        
        data = json.loads(result)
        if "result" in data and "result" in data["result"] and "value" in data["result"]["result"]:
            return data["result"]["result"]["value"]
        return data
    except Exception as e:
        return {"error": str(e)}

def get_chat_state(ws_url):
    js_code = """
    (() => {
        const main = document.querySelector('main');
        if (!main) return JSON.stringify({ error: "No main element found" });
        
        // Extract conversation
        const messages = [];
        const blocks = main.querySelectorAll('div.w-full.flex.flex-col.items-start, div.group.relative.flex.w-full.items-center');
        blocks.forEach(block => {
            const senderEl = block.querySelector('.link, span[role="button"]');
            const sender = senderEl ? senderEl.innerText.trim() : "Me";
            const timeEl = block.querySelector('time');
            const time = timeEl ? timeEl.innerText.trim() : "";
            
            const ps = block.querySelectorAll('p');
            ps.forEach(p => {
                messages.push({
                    sender: sender,
                    senderId: p.getAttribute('data-from') || "me",
                    time: time,
                    text: p.innerText.trim()
                });
            });
        });
        
        // Find action buttons (START, STOP, ESC)
        const buttons = Array.from(main.querySelectorAll('button')).map(el => el.innerText.trim().toUpperCase());
        
        // System alerts
        const alerts = Array.from(main.querySelectorAll('div, span, p')).filter(el => {
            const txt = el.innerText.trim();
            return (txt.includes('chatting with') || txt.includes('skipped') || txt.includes('connecting') || txt.includes('Say hi')) && txt.length < 150;
        }).map(el => el.innerText.trim());
        
        // Extract all visible page text inside main to look for interests/bio
        let pageText = main.innerText.toLowerCase();
        const toRemove = [
            'esc', 'start', 'stop', 'send', 'report', 'confirm', 'get premium',
            'you are now chatting with', 'say hi!', 'your chat partner has skipped',
            'get premium to unlock the gender filter', 'chatting with', 'connecting', 'skipped'
        ];
        for (const phrase of toRemove) {
            pageText = pageText.replaceAll(phrase, '');
        }
        
        return JSON.stringify({ messages, buttons, alerts: [...new Set(alerts)], pageText: pageText.trim() });
    })()
    """
    res = execute_js(ws_url, js_code)
    if isinstance(res, dict) and "error" in res:
        return res
    try:
        return json.loads(res)
    except Exception as e:
        return {"error": f"Failed to parse state: {e}. Raw: {res}"}

def trigger_button(ws_url, button_text):
    js_code = f"""
    (() => {{
        const btn = Array.from(document.querySelectorAll('button')).find(el => {{
            return el.innerText.trim().toUpperCase().includes("{button_text.upper()}");
        }});
        if (btn) {{
            btn.click();
            return "Clicked " + btn.innerText;
        }}
        return "Button not found";
    }})()
    """
    return execute_js(ws_url, js_code)

def trigger_skip(ws_url):
    js_code = """
    (() => {
        const clickConfirm = () => {
            const confirmBtn = Array.from(document.querySelectorAll('button')).find(el => {
                const t = el.innerText.trim().toUpperCase();
                return t.includes("CONFIRM") || t.includes("CONFIRM?");
            });
            if (confirmBtn) {
                confirmBtn.click();
                return true;
            }
            return false;
        };
        
        if (clickConfirm()) return "Clicked CONFIRM immediately";
        
        const esc = Array.from(document.querySelectorAll('button')).find(el => el.innerText.trim().toUpperCase().includes("ESC")) ||
                    Array.from(document.querySelectorAll('kbd')).find(el => el.innerText.trim().toUpperCase() === "ESC");
        
        if (esc) {
            esc.click();
            if (esc.tagName === "KBD" && esc.parentElement) esc.parentElement.click();
        }
        
        // Dispatch Escape key event twice
        const dispatchEscape = () => {
            const eventParams = { key: 'Escape', code: 'Escape', keyCode: 27, which: 27, bubbles: true, cancelable: true };
            document.dispatchEvent(new KeyboardEvent('keydown', eventParams));
            document.dispatchEvent(new KeyboardEvent('keyup', eventParams));
        };
        dispatchEscape();
        dispatchEscape();
        
        // Synchronous retry
        if (clickConfirm()) return "Clicked ESC and CONFIRM synchronously";
        
        // Asynchronous retries to guarantee lightning-fast confirmation
        [10, 30, 50, 80, 120].forEach(ms => {
            setTimeout(clickConfirm, ms);
        });
        
        return "Dispatched skip chain";
    })()
    """
    return execute_js(ws_url, js_code)

def send_message(ws_url, text):
    js_code = f"""
    (() => {{
        const textarea = document.querySelector('textarea[placeholder="Send a message"]') || document.querySelector('textarea');
        if (!textarea) return "No text area found";
        
        // Force element focus
        textarea.focus();
        
        // React custom value setter hack to trigger state update
        const valueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
        if (valueSetter) {{
            valueSetter.call(textarea, {json.dumps(text)});
        }} else {{
            textarea.value = {json.dumps(text)};
        }}
        
        // Dispatch input and change events for framework bindings
        textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
        textarea.dispatchEvent(new Event('change', {{ bubbles: true }}));
        
        // Dispatch keydown, keypress and keyup for Enter key to trigger message submission
        const eventParams = {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true }};
        textarea.dispatchEvent(new KeyboardEvent('keydown', eventParams));
        textarea.dispatchEvent(new KeyboardEvent('keypress', eventParams));
        textarea.dispatchEvent(new KeyboardEvent('keyup', eventParams));
        
        return "Opener dispatched via React hooks";
    }})()
    """
    return execute_js(ws_url, js_code)

def is_male_message(text):
    t = text.lower().strip()
    
    # Explicitly check for f? or f ? variants which indicate a male looking for female
    if "f?" in t or "f ?" in t or "u f" in t or "are you f" in t:
        return True
        
    male_words = ["m", "male", "boy", "guy", "bro", "dude", "man"]
    words = re.findall(r'\b\w+\??\b', t)
    for word in words:
        if word in male_words:
            return True
    if "im m" in t or "i am m" in t or "i\'m m" in t or "m here" in t:
        return True
    return False

def track_skipped(partner, recently_skipped):
    partner_lower = partner.lower().strip()
    if partner_lower not in recently_skipped:
        recently_skipped.append(partner_lower)
        if len(recently_skipped) > 2000:
            recently_skipped.pop(0)

def classify_stranger(name, page_text, recently_skipped=[]):
    name_lower = name.lower().strip()
    
    # Check if this user was recently skipped (to prevent repeated matches)
    if name_lower in recently_skipped:
        return "SKIP", f"Recently skipped username '{name_lower}' repeating"
        
    words = re.findall(r'\b\w+\b', name_lower)
    
    # Check dynamically learned male patterns
    learned = load_learned_patterns()
    learned_names = set(learned.get("names", []))
    learned_roots = set(learned.get("roots", []))
    
    if name_lower in learned_names:
        return "SKIP", f"Learned exact male username '{name_lower}'"
        
    for word in words:
        if word in learned_roots:
            return "SKIP", f"Learned male root word '{word}' detected in username"
            
    # --- 1. SKIP Immediately Rules (Male Names and Keywords) ---
    clearly_male = {
        # Indian male names
        "rahul", "amit", "rohit", "abhishek", "vivek", "sandeep", "vijay", "raj", "anil", "sunil", "sanjay", "ajay", 
        "deepak", "kanishk", "aryan", "sidharth", "siddharth", "arav", "vihaan", "aditya", "krishna", "ram", "shiva", 
        "sharma", "singh", "kumar", "verma", "patel", "shah", "gupta", "mehta", "yadav", "reddy", "nair", "rao",
        "suresh", "ramesh", "mahesh", "ishaan", "dhruv", "kabir", "karan", "dev", "gaurav", "shubham", "sourabh", 
        "saurabh", "aman", "aniket", "kartik", "kunal", "harsh", "ayush", "tushar", "nikhil", "ashish", "pankaj", 
        "mayank", "pranav", "ritik", "piyush", "mohit", "rohan", "yash", "sameer", "samir", "vishal", "vikas", 
        "vikram", "varun", "tarun", "sid", "hardik", "rishabh", "adit", "parth", "chirag", "jatin", "prateek", 
        "pratik", "manish", "nitin", "sachin", "sourav", "sumit", "ankit", "bilal", "aarush", "aarushh", "raaj",
        "parmeet", "gurpreet", "manpreet", "jaspreet", "harpreet", "singh", "singhh", "akash", "aakash", "anurag",
        "harshal", "prashant", "pradeep", "praveen", "pravin", "manoj", "ramesh", "suresh", "dinesh", "umesh",
        "sankalp", "anirudh", "ankush", "aravind", "arvind", "ashok", "avinash", "bablu", "bharat", "bhupendra",
        "chandan", "darshan", "deep", "dharam", "dilip", "gagan", "girish", "gopal", "govind", "gurdev", "hari",
        "harish", "himanshu", "inder", "inderjeet", "jagdish", "jasbir", "jitendra", "kamal", "kapil", "kartikey",
        "kaushal", "kuldeep", "lalit", "madan", "mandeep", "micheal", "mithun", "mukesh", "nakul", "narender",
        "narendra", "naveen", "nitish", "om", "pawan", "prabhat", "pramod", "pratap", "raghav", "rajendra",
        "rajesh", "rajiv", "raju", "rakesh", "ranjeet", "ranjit", "roshan", "rupesh", "sanjeev", "satish",
        "satpal", "satya", "shakti", "shashank", "shekhar", "shravan", "shyam", "sohan", "subhash", "sudhir",
        "sudip", "sujit", "sukhdev", "suraj", "surendra", "suryakant", "tej", "tejas", "uday", "upendra",
        "utkarsh", "vaibhav", "vikrant", "vinay", "vinod", "vipul", "yuvraj",
        # English/Global male names
        "mike", "john", "david", "james", "robert", "william", "joseph", "thomas", "charles", "christopher", 
        "daniel", "matthew", "anthony", "mark", "donald", "steven", "paul", "andrew", "joshua", "kenneth", 
        "kevin", "brian", "george", "timothy", "ronald", "edward", "jason", "jeffrey", "ryan", "jacob", "gary", 
        "nicholas", "eric", "jonathan", "stephen", "larry", "justin", "scott", "brandon", "benjamin", "samuel", 
        "gregory", "frank", "alexander", "raymond", "patrick", "jack", "dennis", "jerry", "tyler", "aaron", 
        "jose", "adam", "nathan", "henry", "douglas", "zachary", "peter", "kyle", "walter", "harold", "jeremy", 
        "carl", "keith", "roger", "gerald", "ethan", "arthur", "albert", "christian", "billy", "lawrence", "joe", 
        "bruce", "willie", "jared", "gabriel", "logan", "alan", "juan", "wayne", "roy", "ralph", "randy", "eugene", 
        "vincent", "russell", "louis", "bobby", "philip", "jonny", "jon", "tom", "tony"
    }
    
    male_substrings = ["bro", "king", "boy", "man", "guy", "dude", "sir", "male", "telugu", "abbai", "abbay", "abbayi"]
    
    # Check words in username for clearly male matches
    words = re.findall(r'\b\w+\b', name_lower)
    for word in words:
        if word in clearly_male:
            return "SKIP", f"Clearly male name '{word}' detected"
            
    # Check male substrings
    for sub in male_substrings:
        if sub in name_lower:
            return "SKIP", f"Male marker '{sub}' detected in username"
            
    # Check for direct male letter indicators (e.g. "Stranger M", ending with " m", starting with "m ", or containing " m ")
    if " m " in f" {name_lower} " or name_lower.endswith(" m") or name_lower.startswith("m "):
        return "SKIP", "Male letter indicator 'M' detected in username"
        
    # Check for male age indicators like m24, m22 at word boundaries
    if re.search(r'\bm\d+', name_lower):
        return "SKIP", "Male age marker (e.g. m24) detected in username"
        
    # Check username is random numbers like "user1829"
    if re.search(r'user\d+', name_lower) or re.match(r'^\d+$', name_lower):
        return "SKIP", "Random number username format detected"
        
    # --- 2. STAY Rules (Female Names and Keywords) ---
    clearly_female = {
        # Indian female names
        "priya", "sara", "emma", "neha", "sofia", "aisha", "pooja", "ananya", "diya", "aanya", "riya", "shruti", 
        "sneha", "tanya", "divya", "kiran", "jyoti", "rhea", "kiara", "kavya", "anika", "isha", "shreya", "sonal", 
        "swati", "megha", "tanvi", "mansi", "aditi", "diksha", "akansha", "akanksha", "kajal", "komal", "shalini", 
        "payal", "prerna", "sakshi", "muskan", "khushi", "simran", "sheetal", "pallavi", "sapna", "monika", "anusha", 
        "rashmi", "kavita", "savita", "babita", "sarita", "pinky", "roshni", "reena", "seema", "chhavi", "barkha", 
        "neetu", "ritu", "anjali", "trupti", "nisha", "preeti", "priti", "lata", "asha", "karina", "kareena", "katrina", 
        "deepika", "aliabhatt", "alia", "shraddha", "anushka", "priyanka", "aishwarya",
        # English/Global female names
        "mary", "patricia", "jennifer", "linda", "elizabeth", "barbara", "susan", "jessica", "sarah", "karen", 
        "nancy", "lisa", "betty", "margaret", "sandra", "ashley", "kimberly", "nicole", "emily", "helen", 
        "michelle", "debra", "amanda", "dorothy", "carol", "melissa", "deborah", "stephanie", "rebecca", "sharon", 
        "laura", "cynthia", "kathleen", "amy", "shirley", "angela", "anna", "brenda", "pamela", "pam", "samantha", 
        "katherine", "christine", "deb", "debbie", "rachel", "carolyn", "janet", "catherine", "heather", "maria", 
        "diane", "virginia", "julie", "joyce", "victoria", "olive", "olivia", "chloe", "sophie", "zoe", "lucy", 
        "lily", "grace", "ruby", "mia", "charlotte"
    }
    
    female_substrings = ["girl", "queen", "baby", "princess"]
    
    for word in words:
        if word in clearly_female:
            return "STAY", f"Clearly female name '{word}' detected"
            
    for sub in female_substrings:
        if sub in name_lower:
            return "STAY", f"Female marker '{sub}' detected in username"
            
    if name_lower.endswith(('a', 'i', 'ya', 'ina')):
        return "STAY", "Username ends with feminine style suffix (-a, -i, -ya, -ina)"
        
    # --- 3. AMBIGUOUS Names (Alex, Sam, Sky, etc.) ---
    female_signals = ["kpop", "makeup", "fashion", "skincare", "astrology", "she/her"]
    male_signals = ["cricket", "gym", "fifa", "cod", "he/him"]
    
    page_text_lower = page_text.lower()
    
    has_female_signal = any(sig in page_text_lower for sig in female_signals)
    has_male_signal = any(sig in page_text_lower for sig in male_signals)
    
    if has_female_signal and not has_male_signal:
        return "STAY", f"Ambiguous name, but female interest/bio signal detected"
    elif has_male_signal and not has_female_signal:
        return "SKIP", f"Ambiguous name, but male interest/bio signal detected"
    elif has_female_signal and has_male_signal:
        return "STAY", f"Ambiguous name with conflicting interest/bio signals (defaulting to STAY)"
    else:
        return "STAY", f"Ambiguous name with no interest/bio signals on screen (defaulting to STAY)"

def is_user_manually_chatting(messages):
    opener = "hey fella ! wassup"
    second_msg = "yo, what name do u go by? 👀"
    me_msgs = [m for m in messages if m["sender"] == "Me"]
    for m in me_msgs:
        if m["text"] != opener and m["text"] != second_msg:
            return True
    if len(me_msgs) > 2:
        return True
    return False

def run_dating_bot():
    print("==================================================")
    print("        CHITCHAT.GG AUTOMATED DATING BOT         ")
    print("==================================================")
    
    current_partner = ""
    last_start_click_time = 0
    skipped_partners = set()
    recently_skipped = []
    
    while True:
        ws_url = get_chitchat_tab()
        if not ws_url:
            print("Waiting for Chitchat tab in Chrome...")
            time.sleep(2)
            continue
            
        chat = get_chat_state(ws_url)
        if "error" in chat:
            print(f"[Bot Error] {chat['error']}")
            time.sleep(1)
            continue
            
        alerts = chat.get("alerts", [])
        buttons = chat.get("buttons", [])
        page_text = chat.get("pageText", "")
        
        # Check active chat partner name from alerts
        chatting_alert = next((a for a in alerts if "chatting with" in a), None)
        is_skipped = any("skipped" in a.lower() for a in alerts)
        is_chatting = chatting_alert is not None and not is_skipped
        
        if is_chatting:
            # Parse partner name using robust regex
            match = re.search(r"You are now chatting with\s+(.+?)(?:\.?\s+Say hi!)?$", chatting_alert, re.IGNORECASE)
            partner = match.group(1).strip() if match else ""
            
            if partner:
                # Case A: Brand new match -> Classify & Opener
                if partner != current_partner:
                    current_partner = partner
                    print(f"\n[Bot] New connection! Matched with: '{partner}'")
                    
                    decision, reason = classify_stranger(partner, page_text, recently_skipped)
                    print(f"[Bot] Decision: {decision} ({reason})")
                    
                    if decision == "SKIP":
                        print(f"[Bot] Skipping '{partner}' immediately...")
                        trigger_skip(ws_url)
                        skipped_partners.add(partner)
                        track_skipped(partner, recently_skipped)
                    else:
                        print(f"[Bot] Staying with '{partner}'! Sending greeting...")
                        send_result = send_message(ws_url, "hey fella ! wassup")
                        print(f"[Bot] {send_result}")
                        print("==================================================")
                
                # Case B: Ongoing match -> Monitor conversation for incoming male signals
                else:
                    if partner in skipped_partners:
                        time.sleep(0.05)
                        continue
                        
                    messages = chat.get("messages", [])
                    
                    # Manual takeover protection: Check if user is manually typing/chatting
                    if is_user_manually_chatting(messages):
                        time.sleep(0.1)
                        continue
                        
                    stranger_msgs = [m["text"] for m in messages if m["sender"] != "Me" and m["sender"] != "System"]
                    me_msgs = [m for m in messages if m["sender"] == "Me"]
                    
                    # 1. Check for male signals first -> skip
                    skipped_any = False
                    for msg in stranger_msgs:
                        if is_male_message(msg):
                            print(f"[Bot] Partner said '{msg}' (sounds male). Skipping immediately!")
                            learn_male_pattern(partner) # Automatically learn pattern!
                            trigger_skip(ws_url)
                            skipped_partners.add(partner)
                            track_skipped(partner, recently_skipped)
                            skipped_any = True
                            break
                            
                    if not skipped_any:
                        # 2. If no male signal, check if we need to send Gen Z name-ask message
                        # We sent exactly 1 message (opener) and the partner replied!
                        if len(me_msgs) == 1 and len(stranger_msgs) >= 1:
                            opener = "hey fella ! wassup"
                            if me_msgs[0]["text"] == opener:
                                print(f"[Bot] Partner replied: '{stranger_msgs[-1]}'. Asking for name in Gen Z style...")
                                send_result = send_message(ws_url, "yo, what name do u go by? 👀")
                                print(f"[Bot] {send_result}")
                                print("==================================================")
                    
        else:
            if current_partner and current_partner not in skipped_partners:
                print(f"[Bot] User manually skipped '{current_partner}'. Learning male pattern...")
                learn_male_pattern(current_partner)
                track_skipped(current_partner, recently_skipped)
            current_partner = ""
            skipped_partners.clear() # Reset since we left chat
            # We are not currently in a chat. Check if we need to click START
            if "START" in buttons:
                now = time.time()
                # Throttle clicks non-blockingly so we don't spam start while keeping loop responsiveness
                if now - last_start_click_time > 0.8:
                    print("[Bot] Idle. Clicking START to find a match...")
                    trigger_button(ws_url, "START")
                    last_start_click_time = now
            elif "ESC" in buttons:
                print("[Bot] Resetting match state...")
                trigger_skip(ws_url)
                
        time.sleep(0.02) # High-speed execution loop

if __name__ == "__main__":
    try:
        run_dating_bot()
    except KeyboardInterrupt:
        print("\nBot stopped by user.")

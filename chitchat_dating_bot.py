import urllib.request
import json
import websocket
import ssl
import sys
import time
import re
import functools

# Force all print statements to flush immediately for real-time IDE logging
print = functools.partial(print, flush=True)

# Common Indian names/roots to identify Indian usernames
INDIAN_ROOTS = [
    "rahul", "amit", "priya", "pooja", "neha", "rohit", "abhishek", "vivek", 
    "sandeep", "vijay", "raj", "anil", "sunil", "sanjay", "ajay", "deepak",
    "kanishk", "aryan", "sidharth", "siddharth", "arav", "vihaan", "aditya",
    "sai", "krishna", "ram", "shiva", "sharma", "singh", "kumar", "verma",
    "patel", "shah", "gupta", "mehta", "yadav", "reddy", "nair", "rao",
    "kaur", "preet", "jeet", "deep", "dev", "ananya", "diya", "aarav",
    "kabir", "isha", "aanya", "arjun", "karan", "riya", "shruti",
    "sneha", "tanya", "divya", "kiran", "jyoti", "suresh", "ramesh", "mahesh",
    "ishaan", "dhruv", "kabir", "rhea", "kiara", "kavya", "isha", "anika"
]
INDIAN_SYMBOLS = ["🧿", "🇮🇳"]

def is_indian_name(name):
    name_lower = name.lower().strip()
    for symbol in INDIAN_SYMBOLS:
        if symbol in name:
            return True
            
    # Check words
    words = re.findall(r'\b\w+\b', name_lower)
    for word in words:
        for root in INDIAN_ROOTS:
            if word == root or (len(word) > 3 and word.startswith(root)) or (len(word) > 3 and root in word):
                return True
    return False

def is_male_name(name):
    n = name.lower()
    # Check for direct male markers in username
    if "(m)" in n or "boy" in n or "guy" in n or "male" in n or "bro" in n or "dude" in n:
        return True
    return False

def is_male_message(text):
    t = text.lower().strip()
    
    # Common male markers
    # "m", "male", "boy", "guy", "bro", "dude", "man"
    # "f?" (stranger asking if we are female means they are likely male)
    male_words = ["m", "male", "boy", "guy", "bro", "dude", "man", "f?", "f ?"]
    
    # Exact word matches
    words = re.findall(r'\b\w+\??\b', t)
    for word in words:
        if word in male_words:
            return True
            
    # Direct phrases
    if "im m" in t or "i am m" in t or "i\'m m" in t or "m here" in t:
        return True
    return False

def is_female_message(text):
    t = text.lower().strip()
    female_words = ["f", "female", "girl", "woman", "lady"]
    words = re.findall(r'\b\w+\b', t)
    for word in words:
        if word in female_words:
            return True
    if "im f" in t or "i am f" in t or "i\'m f" in t:
        return True
    return False

def get_chitchat_tab():
    try:
        response = urllib.request.urlopen("http://127.0.0.1:9222/json")
        pages = json.loads(response.read().decode())
        for page in pages:
            if "chitchat" in page.get("url", "").lower() or "chitchat" in page.get("title", "").lower():
                return page.get("webSocketDebuggerUrl")
    except Exception as e:
        pass
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
        
        const buttons = Array.from(main.querySelectorAll('button')).map(el => el.innerText.trim().toUpperCase());
        
        const alerts = Array.from(main.querySelectorAll('div, span, p')).filter(el => {
            const txt = el.innerText.trim();
            return (txt.includes('chatting with') || txt.includes('skipped') || txt.includes('connecting') || txt.includes('Say hi')) && txt.length < 150;
        }).map(el => el.innerText.trim());
        
        return JSON.stringify({ messages, buttons, alerts: [...new Set(alerts)] });
    })()
    """
    res = execute_js(ws_url, js_code)
    if isinstance(res, dict):
        if "error" in res:
            return res
        # If the result itself has exception details
        if "result" in res and "exceptionDetails" in res["result"]:
            return {"error": f"JS Exception: {res['result']['exceptionDetails']}"}
        return {"error": f"CDP returned raw dictionary: {res}"}
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
        // 1. Check if CONFIRM? is present and click it
        const confirmBtn = Array.from(document.querySelectorAll('button')).find(el => {
            const t = el.innerText.trim().toUpperCase();
            return t.includes("CONFIRM") || t.includes("CONFIRM?");
        });
        if (confirmBtn) {
            confirmBtn.click();
            return "Clicked CONFIRM";
        }
        
        // 2. Otherwise click ESC kbd or parent
        const kbd = Array.from(document.querySelectorAll('kbd')).find(el => el.innerText.trim().toUpperCase() === "ESC");
        if (kbd) {
            kbd.click();
            if (kbd.parentElement) kbd.parentElement.click();
            return "Clicked KBD ESC";
        }
        
        // 3. Fallback: Dispatch Escape keyboard event
        const eventParams = {
            key: 'Escape', code: 'Escape', keyCode: 27, which: 27, bubbles: true, cancelable: true
        };
        document.dispatchEvent(new KeyboardEvent('keydown', eventParams));
        document.dispatchEvent(new KeyboardEvent('keyup', eventParams));
        return "Dispatched Escape key event";
    })()
    """
    return execute_js(ws_url, js_code)

def send_message(ws_url, text):
    js_code = f"""
    (() => {{
        const textarea = document.querySelector('textarea[placeholder="Send a message"]');
        if (!textarea) return "No text area found";
        textarea.value = {json.dumps(text)};
        textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
        
        const form = textarea.closest('form');
        if (form) {{
            form.dispatchEvent(new Event('submit', {{ bubbles: true }}));
            return "Form submitted";
        }}
        return "Text entered";
    }})()
    """
    return execute_js(ws_url, js_code)

def main_loop():
    print("==================================================")
    print("      CHITCHAT DATING BOT RUNNING                ")
    print("==================================================")
    
    # State tracking: 
    # 'IDLE': matching not active
    # 'GREETED': sent 'hi', waiting for reply
    # 'HINTED': sent 'M here, you?', waiting for reply
    current_state = 'IDLE'
    last_processed_msg_count = 0
    current_partner = ""
    
    while True:
        ws_url = get_chitchat_tab()
        if not ws_url:
            print("Waiting for Chitchat tab in Chrome...")
            time.sleep(2)
            continue
            
        chat = get_chat_state(ws_url)
        if "error" in chat:
            print(f"[Bot Error] {chat['error']}")
            time.sleep(2)
            continue
            
        alerts = chat.get("alerts", [])
        messages = chat.get("messages", [])
        buttons = chat.get("buttons", [])
        
        # Check active chat partner name from alerts
        chatting_alert = next((a for a in alerts if "chatting with" in a), None)
        is_chatting = chatting_alert is not None and not any("skipped" in a.lower() for a in alerts)
        
        if is_chatting:
            # Parse partner name
            # "You are now chatting with [Partner]. Say hi!"
            partner = chatting_alert.replace("You are now chatting with", "").replace(". Say hi!", "").strip()
            
            # If we just connected or partner changed
            if partner != current_partner:
                current_partner = partner
                last_processed_msg_count = 0
                print(f"\n[Bot] Matched with: {partner}")
                
                # Rule 1: Check if name sounds Indian
                if is_indian_name(partner):
                    print(f"[Bot] Username '{partner}' sounds Indian. Skipping immediately!")
                    trigger_skip(ws_url)
                    current_state = 'IDLE'
                    current_partner = ""
                    time.sleep(1.5)
                    continue
                    
                # Rule 2: Greet immediately
                print(f"[Bot] Sending greeting...")
                send_message(ws_url, "hi")
                current_state = 'GREETED'
                last_processed_msg_count = len(messages)
                continue
                
            # We are chatting with the current partner
            # Check for new messages from the stranger
            stranger_msgs = [m for m in messages if m["sender"] != "Me" and m["sender"] != "System"]
            
            if len(stranger_msgs) > 0:
                last_stranger_msg = stranger_msgs[-1]["text"]
                
                # Check if we have new un-analyzed messages
                if len(messages) > last_processed_msg_count:
                    last_processed_msg_count = len(messages)
                    print(f"[{partner}]: {last_stranger_msg}")
                    
                    # Rule 3: Skip if message indicates male
                    if is_male_message(last_stranger_msg):
                        print(f"[Bot] Partner said '{last_stranger_msg}' (sounds male). Skipping!")
                        trigger_skip(ws_url)
                        current_state = 'IDLE'
                        current_partner = ""
                        time.sleep(1.5)
                        continue
                        
                    # Check if they confirmed they are female
                    if is_female_message(last_stranger_msg):
                        print(f"\n🎉 [Bot] SUCCESS! Found a female match: '{partner}'!")
                        print(f"[Bot] Last message: '{last_stranger_msg}'")
                        print("==================================================")
                        print("    BOT PAUSED. PLEASE TAKE OVER IN CHROME!       ")
                        print("==================================================")
                        # Sound the bell / alert
                        print("\a\a\a")
                        break
                        
                    # Handle state machine reply turns
                    if current_state == 'GREETED':
                        # Send male hint
                        print("[Bot] Sending male hint...")
                        send_message(ws_url, "M here, you?")
                        current_state = 'HINTED'
                        
                    elif current_state == 'HINTED':
                        # They replied to our hint, but didn't say F, nor M.
                        # Let's prompt gently: "are you f?"
                        print("[Bot] Prompting for gender...")
                        send_message(ws_url, "f?")
                        current_state = 'GENDER_PROMPTED'
                        
                    elif current_state == 'GENDER_PROMPTED':
                        # If we prompted and they still didn't say F/girl/etc., they might be wasting time or M. Skip.
                        print("[Bot] No clear gender indication after prompt. Skipping.")
                        trigger_skip(ws_url)
                        current_state = 'IDLE'
                        current_partner = ""
                        time.sleep(1.5)
                        
        else:
            # We are not in a chat (idle or skipped)
            current_partner = ""
            current_state = 'IDLE'
            
            # Check if START button is available to match
            if "START" in buttons:
                print("[Bot] Idle. Clicking START to match...")
                trigger_button(ws_url, "START")
                time.sleep(2)
            else:
                # Sometimes Chitchat shows SKIP or ESC even when skipped, let's press ESC to start matching
                print("[Bot] Attempting to initiate match...")
                trigger_button(ws_url, "START")
                time.sleep(1.5)
                
        time.sleep(0.5)

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\nBot stopped by user.")

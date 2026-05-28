import urllib.request
import json
import websocket
import ssl
import sys

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
    ws = websocket.create_connection(ws_url, sslopt={"cert_reqs": ssl.CERT_NONE}, suppress_origin=True)
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

if __name__ == "__main__":
    ws_url = get_chitchat_tab()
    if not ws_url:
        print("Chitchat tab not found. Make sure Chitchat is open in Chrome.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Connected to Chitchat tab WebSocket: {ws_url}")
    # Get inputs and buttons on the page
    js_code = """
    (() => {
        const kbd = Array.from(document.querySelectorAll('kbd')).find(el => el.innerText.trim().toUpperCase() === "ESC");
        let clicked = [];
        if (kbd) {
            kbd.click();
            clicked.push("KBD");
            const parent = kbd.parentElement;
            if (parent) {
                parent.click();
                clicked.push("PARENT");
            }
        }
        
        // Dispatch Escape key events
        const eventParams = {
            key: 'Escape',
            code: 'Escape',
            keyCode: 27,
            which: 27,
            bubbles: true,
            cancelable: true
        };
        
        const escDown = new KeyboardEvent('keydown', eventParams);
        document.dispatchEvent(escDown);
        
        const escUp = new KeyboardEvent('keyup', eventParams);
        document.dispatchEvent(escUp);
        
        return "Clicked: " + clicked.join(", ") + " and dispatched ESC key events";
    })()
    """
    dom_info_str = execute_js(ws_url, js_code)
    try:
        dom_info = json.loads(dom_info_str)
        print("\n--- DOM INFO ---")
        print(json.dumps(dom_info, indent=2))
    except Exception as e:
        print("Raw response:", dom_info_str)
    print("--------------------")

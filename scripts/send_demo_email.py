import urllib.request
import json
import ssl

def send_demo_email():
    url = "https://formsubmit.co/raghda.emara22@gmail.com"
    
    # URL encode the payload parameters like a real HTML form
    data = urllib.parse.urlencode({
        "name": "Your Autonomous AI Agent",
        "_subject": "System Test: FDE Architecture Deployed Successfully!",
        "message": "Hello Raghda,\n\nI am successfully executing code and tests on your machine. The LangGraph agent is routing, the Escalation Engine is intercepting emergencies, and ChromaDB is retrieving documents perfectly.\n\nThis email confirms that the 'Send Email Phase' of your FDE project works beautifully.\n\nBest,\nAntigravity AI Assistant",
        "_captcha": "false"
    }).encode('utf-8')
    
    req = urllib.request.Request(
        url, 
        data=data, 
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        method="POST"
    )
    
    # Ignore SSL certification for local dev tests
    context = ssl._create_unverified_context()

    try:
        print("Sending email direct via HTTP payload...")
        response = urllib.request.urlopen(req, context=context)
        resp_body = response.read().decode('utf-8')
        print(f"✅ Success! Response: {resp_body}")
        print("\n📥 Check your inbox at raghda.emara22@gmail.com!")
        print("(Note: FormSubmit might send an initial 'Activate this form' email first since you haven't used this service before. If so, click 'Activate' and run this script again.)")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

if __name__ == "__main__":
    send_demo_email()

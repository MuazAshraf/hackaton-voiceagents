VoiceOps Guardian — an autonomous recovery agent for voice AI
Locked. We’re building:
VoiceForm — Adaptive Multimodal Booking Agent
Core rule:
Voice capture → confirm once → if incorrect, open form → typed data becomes source of truth → book through Cal.com
At hackathon start, implementation order will be:
Frontend with Vapi Web SDK
Shared session_id
showContactForm client-side tool
Contact form modal
Backend session/contact storage
Modify booking endpoint to use verified typed data
Gmail confirmation
Slack audit/escalation
Final reliability tests and two-minute demo
Keep the existing Vapi assistant, four tools, backend and Cloudflare setup. Don’t delete anything.
Since the event officially starts at 9 PM, safest competition-integrity choice is to wait before implementing the new core feature. At 9, send me “start VoiceForm”, and we’ll build it directly in hackaton-voice/.
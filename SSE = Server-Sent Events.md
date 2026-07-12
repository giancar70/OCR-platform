SSE = Server-Sent Events
  
  It's a protocol where the server pushes data to the browser over a single HTTP connection that stays open.

  How it works:

  Browser                          Server
    │                                │
    │── GET /stream ────────────────►│
    │                                │
    │◄── data: {"status":"processing"}│  (when OCR starts)
    │                                │
    │◄── data: {"status":"completed"} │  (when OCR finishes)
    │                                │
    │◄── : ping ─────────────────────│  (every 5s to keep alive)
    │                                │
    │── close() ────────────────────►│  (browser closes when done)

  Why SSE instead of polling:   

  ┌──────────────────────────────────────────────┬────────────────────────────────────────────────────────────┐
  │                   Polling                    │                            SSE                             │
  ├──────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ Browser asks every N seconds "are you done?" │ Server tells the browser the moment something changes      │
  ├──────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ Wasteful — most requests return "not yet"    │ Efficient — only sends data when there's something to send │
  ├──────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ Adds delay (up to N seconds)                 │ Instant update                                             │
  └──────────────────────────────────────────────┴────────────────────────────────────────────────────────────┘
  
  Why SSE instead of WebSocket:

  ┌────────────────────────┬─────────────────────────────────┐
  │       WebSocket        │               SSE               │
  ├────────────────────────┼─────────────────────────────────┤
  │ Two-way communication  │ One-way (server → browser only) │
  ├────────────────────────┼─────────────────────────────────┤
  │ More complex           │ Simpler, works over plain HTTP  │
  ├────────────────────────┼─────────────────────────────────┤
  │ Needed for chat, games │ Perfect for status updates      │
  └────────────────────────┴─────────────────────────────────┘
  
  In this project SSE is the right choice because the browser only needs to receive updates (OCR status changes) — it never needs to send data
  back through the same connection.
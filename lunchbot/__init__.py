"""lunchbot: picks where the team goes for lunch and who drives.

`core` holds the bot logic and never talks to a chat service. Each chat platform
lives in `adapters/` and turns core `Message`s into that platform's format.
"""

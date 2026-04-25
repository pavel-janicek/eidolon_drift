import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from eidolon.game_loop import Game

# scripts/test_game_messages.py
g = Game()   # nevyžaduje curses
print("messages after init:", g.messages)
# try push_message if exists
if hasattr(g, "push_message"):
    g.push_message("[test] push_message works")
    print("messages after push:", g.messages)
else:
    print("No push_message method on Game")

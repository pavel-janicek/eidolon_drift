# Eidolon Drift

**Version 1.4.0** - A Terminal-Based Incident Response Game

** Controller supported game ***


*This game was written by AI (GitHub Copilot) with human guidance and testing.*

## Overview

Eidolon Drift is a terminal-based adventure game where you play as an incident responder on a distressed spaceship. Your mission is to navigate through the vessel, reach the Command Module, and escape using the emergency pod.

The game features atmospheric horror elements with sanity mechanics that affect your perception of the environment. As your sanity decreases, your field of vision shrinks, creating a tense exploration experience.

## Features

- **Terminal-Based Gameplay**: Full curses interface with color support
- **Procedural Map Generation**: Each playthrough features a unique ship layout
- **Sanity System**: Your mental state affects vision range and gameplay
- **Interactive Environment**: Explore different ship sectors with unique characteristics
- **Atmospheric Messaging**: Ambient messages and events create immersion
- **Comprehensive Help System**: In-game commands for navigation and information

## Game Mechanics

### Joystick support
- To add new joystick run from project root `PYTHONPATH=$(pwd) python3 -m eidolon.io.input_handler --map-test`
- Check mapping of your joystick and add its support to data/controllers as a JSON file

### Movement & Controls
- **WASD**: Move up/down/left/right
- **Commands**: Type `h` for available commands
- **Quit**: Press 'q' to exit

### Sanity System
- Sanity starts at 100 and decreases over time
- Low sanity reduces your field of vision
- Certain areas (like anomalies) accelerate sanity loss
- Medbay sectors restore sanity

### Vision System
- Full visibility at 100 sanity
- Vision radius shrinks to minimum 20% as sanity decreases
- Areas outside vision appear as empty space

### Objectives
- Unlock Escape pod
- Navigate to the Command Module
- Use the escape pod to complete the mission
- Survive environmental hazards and maintain sanity

## Installation

### Prerequisites
- Python 3.6+ (tested on 3.6-3.13)
- Terminal with curses support (Linux/macOS/Windows WSL)
- pygame installed

### Setup
1. Clone or download the project
2. Navigate to the project directory
3. Run the game:
   ```bash
   python main.py
   ```

### Windows Users
If you encounter curses-related errors on Windows:

1. **Install windows-curses** (recommended):
   ```bash
   pip install windows-curses
   ```

2. **Alternative**: The game includes fallback text mode that works without curses:
   - Run normally: `python main.py` (will auto-detect and use text mode if curses unavailable)
   - Text mode provides basic command-line interface

### Dependencies
The game uses only standard Python libraries:
- `curses` (built-in on Unix systems, install `windows-curses` on Windows)
- `pathlib` (Python 3.4+)
- `random` (built-in)
- `json` (built-in)


## Configuration

Game settings can be modified in `eidolon/config.py`:

- `SEED`: Set for reproducible map generation
- `TICKS_TO_SCAN`: How long should "Scanning" sector take
- `FRAME_TIME`: For CPU load. 1/30 == 30 FPS
- `LOG_LEVEL`: Lowest level of logged things. Most loggers are in game set to DEBUG, but main errors/crashesh have WARN/ERROR
- `GAME_VERSION`: Current version number
- Map generation parameters for customization

## Development

This game was developed using AI assistance (GitHub Copilot) with iterative human testing and refinement. The codebase demonstrates:

- Modular Python architecture
- Terminal UI development with curses
- Procedural content generation
- Event-driven game systems
- Sanity/vision mechanics implementation

## Contributing

As an AI-generated project, contributions are welcome! Areas for improvement:

- Additional ship sectors and events
- Enhanced sanity mechanics
- More interactive objects
- Sound effects (if terminal audio is added)
- Cross-platform compatibility improvements

## License

This project is open source. Feel free to use, modify, and distribute.

## Credits

- **AI Author**: GitHub Copilot + Microsoft Copilot
- **Human Testing & Refinement**: Manual playtesting and bug fixes
- **Inspiration**: Terminal-based games like Dwarf Fortress, NetHack

---

*Experience the tension of space exploration in your terminal. How long can you maintain your sanity aboard the Eidolon?*
# DID Character Sheet

**DID Character Sheet** is a Windows desktop character-sheet application designed to make playing a character faster, clearer, and more enjoyable at the table.

The idea is simple: instead of using a static PDF or constantly looking through rulebooks, the app keeps the character's important information, improvements, notes, inventory, resources, and dice in one interactive place.

It is built around a parchment-style fantasy interface and is intended to feel like a real character sheet rather than a generic database or spreadsheet.

## What the app does

The character sheet keeps track of the parts of a character that change during play, while also presenting the rules and descriptions needed to use them.

Main features include:

- Interactive character sheet with editable character information
- Hearts / HP and Adversity Token tracking
- Abilities and Improvements
- Empowerments and leveled upgrades
- Heightened Abilities with automatic IP-cost handling
- Inventory management
- Player notes and automatically generated system notes
- Linked notes for Improvements and inventory items
- Animal Buddy support with its own dedicated sheet
- Built-in dice roller with ordinary dice and a physical d100
- Roll history for the current session
- Light and dark themes
- Character save/load support
- Character creation rules and templates
- Automatic update checking through GitHub

## Improvements and rules

One of the main goals of the app is to reduce the need to repeatedly search through rules during play.

Improvement descriptions, empowerment text, costs, and formatting are stored centrally and displayed where they are relevant. Purchased Improvements can also create system notes automatically, so important rules remain available without cluttering the main character sheet.

The app also handles special rules such as:

- Improvement Point costs
- Heightened Ability progression
- Empowerment dependencies
- Purchase limits
- Free versus paid upgrades
- Character-creation restrictions

When the displayed IP cost and the amount that will actually be spent do not match, the app warns the player before the purchase is completed.

## Notes

Notes are designed to work as part of the character sheet rather than as a separate text editor.

Players can:

- Create their own notes
- Change note colors
- Pin important notes
- Use bold, italic, and underline formatting
- Add custom note icons
- Link notes to Improvements or inventory items

System notes are kept separate from player notes and are generated from the app's rule data.

## Dice roller

The app includes an integrated animated dice roller.

Ordinary dice are rolled through DiceBox, while the d100 uses its own physical 3D die whose result is determined by its final orientation.

Other-dice rolls are displayed by die type, for example:

```text
d4: 3, 2, 3
d6: 5, 1
d100: 81
```

The app does not combine these into a single total unless the specific game roll requires one.

Previous rolls are kept only for the current app session.

## Improvement Editor

The built-in **Improvement Editor** allows the catalog of Improvements and Empowerments to be maintained without manually editing source files.

It supports direct editing of:

- Improvement names
- Costs
- Tags
- Picker descriptions
- Character-sheet descriptions
- Player choices
- Empowerments
- Leveled / scaling empowerments
- Purchase limits

Changes can be saved locally as a draft.

The app also supports an optional online suggestion system using Supabase, allowing catalog changes to be submitted and reviewed before they are accepted.

## Design goals

The project is built around a few principles:

**Keep play fast.**  
Information that matters during play should be visible or reachable with very few clicks.

**Keep the sheet readable.**  
The interface should feel like a fantasy character sheet, not an administrative program.

**Keep rules consistent.**  
Rule descriptions and Improvement content should come from one authoritative source rather than being duplicated throughout the UI.

**Automate bookkeeping, not decisions.**  
The app should calculate costs, enforce limits, and warn about invalid actions while still leaving meaningful character choices to the player.

**Preserve player control.**  
Players can organize notes, colors, icons, inventory, and character presentation without changing the underlying game rules.

## Technology

The desktop application is written primarily in:

- Python
- PySide6 / Qt
- Qt WebEngine
- HTML / JavaScript for the dice roller
- DiceBox for ordinary 3D dice
- Custom JavaScript physics for the d100

Optional online Improvement suggestions use Supabase.

## Updates

The app checks GitHub for new releases.

When a new version is installed, the GitHub release description can be shown inside the app as a **What's New** message, making it easy for players to see what changed.

## Project status

DID Character Sheet is under active development.

The application already contains the main character-management, Improvement, notes, inventory, dice, and editor systems, while new releases continue to improve usability, visual consistency, performance, and automated testing.

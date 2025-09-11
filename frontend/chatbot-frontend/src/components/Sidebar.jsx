import React from 'react';

export default function Sidebar() {
  return (
    <nav className="sidebar" aria-label="Tools sidebar">
      <h1>Adventurer's Tools</h1>
      <button className="nav-btn" aria-label="Roll Dice" onClick={() => {/* TODO */}} disabled>
        🎲 Roll Dice
      </button>
      <button className="nav-btn" aria-label="Character Sheet" onClick={() => {/* TODO */}} disabled>
        📜 Character Sheet
      </button>
      <button className="nav-btn" aria-label="HP and MP" onClick={() => {/* TODO */}} disabled>
        ❤️ HP / 🔮 MP
      </button>
    </nav>
  );
}


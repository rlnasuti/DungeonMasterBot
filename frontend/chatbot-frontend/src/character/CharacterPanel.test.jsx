import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { CharacterPanel } from './index';

const gameState = {
  state_version: 42,
  players: [
    {
      id: 'player-one',
      display_name: 'Player One',
      character: {
        name: 'Aria',
        class_name: 'Wizard',
        subclass_name: 'School of Evocation',
        ruleset_id: 'srd-5.2.1',
        level: 3,
        ancestry: 'High Elf',
        background: 'Sage',
        alignment: 'chaotic_good',
        size: 'medium',
        experience_points: 900,
        heroic_inspiration: true,
        death_saves: { successes: 2, failures: 1 },
        hp: { current: 8, max: 12, temp: 3 },
        armor_class: 16,
        proficiency_bonus: 2,
        speed: { walk: 30 },
        passive_perception: 13,
        abilities: {
          strength: { score: 8, modifier: -1 },
          dexterity: { score: 14, modifier: 2 },
          intelligence: { score: 17, modifier: 3 },
        },
        saving_throws: [
          { name: 'Intelligence', modifier: 5 },
          { name: 'Wisdom', modifier: 2 },
        ],
        skills: [
          { name: 'Arcana', modifier: 5 },
          { name: 'Perception', modifier: 3 },
        ],
        proficiencies: {
          armor: ['light armor'],
          weapons: ['longswords', 'shortbows'],
          tools: ['calligrapher supplies'],
          languages: ['Common', 'Elvish'],
        },
        conditions: ['Poisoned'],
        hit_dice: { available: 2, max: 3, die: 'd6' },
        spell_slots: [
          { level: 1, used: 1, max: 2 },
          { level: 2, used: 0, max: 1 },
        ],
        class_resources: [{ name: 'Arcane Recovery', current: 1, max: 1 }],
        currency: { gp: 25, sp: 4 },
        inventory: [
          {
            item_id: 'armor-studded',
            name: 'Studded Leather',
            quantity: 1,
            equipped: true,
            category: 'armor',
            armor_category: 'light armor',
            armor_class: 12,
            weight: 13,
            rules_ref: 'Equipment: Armor',
          },
          {
            item_id: 'shield-oak',
            name: 'Oak Shield',
            quantity: 1,
            equipped: true,
            category: 'shield',
            armor_class_bonus: 2,
          },
          {
            item_id: 'focus-wand',
            name: 'Ash Wand',
            quantity: 1,
            equipped: true,
            category: 'arcane focus',
          },
          { item_id: 'spellbook', name: 'Spellbook', quantity: 1, equipped: false },
        ],
        armor_class_calculation: {
          base: 12,
          use_dexterity: true,
          dexterity_cap: 2,
          shield_bonus: 2,
          misc_bonus: 0,
          source_item_ids: ['armor-studded', 'shield-oak'],
          description: 'Studded leather, Dexterity, and shield.',
        },
        attacks: [
          {
            attack_id: 'attack-longbow',
            name: 'Longbow',
            attack_type: 'ranged weapon',
            attack_bonus: 4,
            damage: [{ dice: '1d8', bonus: 2, damage_type: 'piercing' }],
            range_normal: 150,
            range_long: 600,
            source_item_id: 'longbow-missing-from-inventory',
            properties: ['ammunition', 'heavy', 'two-handed'],
          },
          {
            attack_id: 'attack-quarterstaff',
            name: 'Quarterstaff',
            attack_type: 'melee_weapon',
            attack_bonus: 1,
            damage: [{ dice: '1d6', bonus: -1, damage_type: 'bludgeoning' }],
            reach: 5,
            range_normal: null,
            range_long: null,
            source_item_id: null,
            properties: ['versatile'],
          },
        ],
        features: [
          {
            feature_id: 'feature-sculpt-spells',
            name: 'Sculpt Spells',
            source: 'Wizard 2',
            rules_ref: 'Evocation Savant',
            summary: 'Protect chosen creatures from your evocation spells.',
          },
        ],
        spellcasting: {
          ability: 'intelligence',
          save_dc: 13,
          attack_bonus: 5,
          preparation_mode: 'spellbook prepared',
          known_spell_ids: ['spell-fire-bolt'],
          prepared_spell_ids: ['spell-mage-armor'],
          always_prepared_spell_ids: ['spell-mage-armor'],
          spellbook_spell_ids: ['spell-mage-armor', 'spell-detect-magic'],
          ritual_casting: true,
          focus_item_id: 'focus-wand',
          spells: [
            {
              spell_id: 'spell-fire-bolt',
              name: 'Fire Bolt',
              level: 0,
              school: 'evocation',
              source: 'Wizard',
              casting_time: '1 action',
              range: '120 feet',
              duration: 'Instantaneous',
              components: ['V', 'S'],
              concentration: false,
              ritual: false,
              rules_ref: 'Spells: Fire Bolt',
            },
            {
              spell_id: 'spell-mage-armor',
              name: 'Mage Armor',
              level: 1,
              school: 'abjuration',
              source: 'Wizard',
              casting_time: '1 action',
              range: 'Touch',
              duration: '8 hours',
              components: ['V', 'S', 'M'],
              concentration: false,
              ritual: false,
              rules_ref: 'Spells: Mage Armor',
            },
            {
              spell_id: 'spell-detect-magic',
              name: 'Detect Magic',
              level: 1,
              school: 'divination',
              source: 'Wizard',
              casting_time: '1 action',
              range: 'Self',
              duration: 'Concentration, up to 10 minutes',
              components: ['V', 'S'],
              concentration: true,
              ritual: true,
              rules_ref: 'Spells: Detect Magic',
            },
          ],
        },
      },
    },
    {
      id: 'player-two',
      display_name: 'Player Two',
      character: {
        name: 'Bram',
        class_name: 'Fighter',
        level: 3,
        hp: { current: 24, max: 28, temp: 0 },
        armor_class: 18,
        abilities: { strength: { score: 16, modifier: 3 } },
        saving_throws: [{ name: 'Strength', modifier: 5 }],
        skills: [{ name: 'Athletics', modifier: 5 }],
        conditions: [],
        hit_dice: { available: 3, max: 3, die: 'd10' },
        class_resources: [{ name: 'Second Wind', current: 0, max: 1 }],
        inventory: ['Longsword', 'Shield'],
      },
    },
  ],
  pending_roll: {
    id: 'roll-7',
    player_id: 'player-one',
    label: 'Investigate the runes',
    die: 'd20',
    modifier: 5,
  },
};

function createApi(submitResult = { ...gameState, state_version: 43, pending_roll: null }) {
  return {
    getGameState: jest.fn().mockResolvedValue(gameState),
    submitPhysicalRoll: jest.fn().mockResolvedValue(submitResult),
  };
}

async function setupPanel(api = createApi()) {
  render(
    <CharacterPanel
      sessionId="session-one"
      api={api}
      pollIntervalMs={0}
    />,
  );
  const firstTab = await screen.findByRole('tab', { name: /Player One/i });
  await waitFor(() => expect(firstTab).toHaveAttribute('aria-selected', 'true'));
  return api;
}

function selectSheetTab(name) {
  fireEvent.click(screen.getByRole('tab', { name, exact: true }));
}

test('renders current, maximum, and temporary hit points accessibly', async () => {
  await setupPanel();

  const hp = screen.getByRole('progressbar', { name: /Aria hit points/i });
  expect(hp).toHaveAttribute('aria-valuenow', '8');
  expect(hp).toHaveAttribute('aria-valuemax', '12');
  expect(screen.getByText('8 / 12')).toBeInTheDocument();
  expect(screen.getByText('Temp HP: 3')).toBeInTheDocument();
});

test('shows used and available spell slots', async () => {
  await setupPanel();
  selectSheetTab('Spells');

  expect(screen.getByText('1 used, 1 available')).toBeInTheDocument();
  expect(screen.getByText('0 used, 1 available')).toBeInTheDocument();
});

test('shows the authoritative coin purse on the character sheet', async () => {
  await setupPanel();
  selectSheetTab('Inventory');

  const purse = screen.getByRole('list', { name: /Aria currency/i });
  expect(purse).toHaveTextContent('25 gp');
  expect(purse).toHaveTextContent('4 sp');
  expect(purse).toHaveTextContent('0 pp');
});

test('provides accessible keyboard navigation between character sheet sections', async () => {
  await setupPanel();

  const coreTab = screen.getByRole('tab', { name: 'Core', exact: true });
  const featuresTab = screen.getByRole('tab', { name: 'Features', exact: true });
  const corePanel = screen.getByRole('tabpanel', { name: 'Core', exact: true });
  const featuresPanel = document.getElementById('character-sheet-panel-player-one-features');

  expect(coreTab).toHaveAttribute('aria-selected', 'true');
  expect(coreTab).toHaveAttribute('aria-controls', corePanel.id);
  expect(corePanel).toHaveAttribute('aria-labelledby', coreTab.id);
  expect(featuresPanel).toHaveAttribute('hidden');
  expect(screen.queryByRole('region', { name: /Features & traits/i })).not.toBeInTheDocument();
  expect(screen.queryByRole('region', { name: /Aria spellcasting/i })).not.toBeInTheDocument();
  expect(screen.queryByRole('list', { name: /Aria currency/i })).not.toBeInTheDocument();

  coreTab.focus();
  fireEvent.keyDown(coreTab, { key: 'ArrowRight' });

  expect(featuresTab).toHaveFocus();
  expect(featuresTab).toHaveAttribute('aria-selected', 'true');
  expect(corePanel).toHaveAttribute('hidden');
  expect(screen.getByRole('tabpanel', { name: 'Features', exact: true })).toBeVisible();
  expect(screen.getByRole('region', { name: /Features & traits/i })).toBeVisible();
});

test('renders the enriched D&D combat, proficiency, feature, and spell details', async () => {
  await setupPanel();

  expect(screen.getByText(/Wizard — School of Evocation · Level 3/i)).toBeInTheDocument();
  expect(screen.getByText(/High Elf · Medium · Sage · Chaotic Good · 900 XP · SRD 5.2.1/i)).toBeInTheDocument();

  const recovery = screen.getByText('Death saves').closest('dl');
  expect(recovery).toHaveTextContent('2 successes · 1 failure');
  expect(recovery).toHaveTextContent('Heroic inspirationAvailable');

  const statistics = screen.getByRole('region', { name: /Aria core statistics/i });
  expect(statistics).toHaveTextContent('Initiative+2');
  expect(statistics).toHaveTextContent('Speed30 ft.');
  expect(statistics).toHaveTextContent('Passive Perception13');
  expect(statistics).toHaveTextContent('Proficiency+2');

  const defense = screen.getByRole('region', { name: /Armor & defense/i });
  expect(defense).toHaveTextContent('Studded Leather');
  expect(defense).toHaveTextContent('Oak Shield');
  expect(defense).toHaveTextContent('Base AC12');
  expect(defense).toHaveTextContent('Dexterity+2 (maximum +2)');

  const attacks = screen.getByRole('list', { name: /Aria attacks/i });
  expect(attacks).toHaveTextContent('Longbow');
  expect(attacks).toHaveTextContent('+4 to hit');
  expect(attacks).toHaveTextContent('1d8 + 2 piercing');
  expect(attacks).toHaveTextContent('150/600 ft.');
  expect(attacks).toHaveTextContent('5 ft. reach');
  expect(attacks).toHaveTextContent('Two Handed');

  selectSheetTab('Features');
  const proficiencySection = screen.getByRole('region', { name: /Proficiencies & languages/i });
  expect(proficiencySection).toHaveTextContent('Light Armor');
  expect(proficiencySection).toHaveTextContent('Calligrapher Supplies');
  expect(proficiencySection).toHaveTextContent('Elvish');

  const features = screen.getByRole('region', { name: /Features & traits/i });
  expect(features).toHaveTextContent('Sculpt Spells');
  expect(features).toHaveTextContent('Protect chosen creatures');

  selectSheetTab('Spells');
  const spellcasting = screen.getByRole('region', { name: /Aria spellcasting/i });
  expect(spellcasting).toHaveTextContent('AbilityIntelligence');
  expect(spellcasting).toHaveTextContent('Save DC13');
  expect(spellcasting).toHaveTextContent('Spell attack+5');
  expect(spellcasting).toHaveTextContent('FocusAsh Wand');

  const fireBolt = within(spellcasting).getByRole('article', { name: /Fire Bolt spell/i });
  expect(fireBolt).toHaveTextContent('Known');
  expect(fireBolt).toHaveTextContent('Evocation · Wizard');
  expect(fireBolt).toHaveTextContent('1 action');
  expect(fireBolt).toHaveTextContent('120 feet');
  expect(fireBolt).toHaveTextContent('V, S');

  const mageArmor = within(spellcasting).getByRole('article', { name: /Mage Armor spell/i });
  expect(mageArmor).toHaveTextContent('Prepared');
  expect(mageArmor).toHaveTextContent('Always prepared');
  expect(mageArmor).toHaveTextContent('Spellbook');

  const detectMagic = within(spellcasting).getByRole('article', { name: /Detect Magic spell/i });
  expect(detectMagic).toHaveTextContent('Concentration');
  expect(detectMagic).toHaveTextContent('Ritual');

  selectSheetTab('Inventory');
  const inventory = screen.getByRole('region', { name: /Inventory/i });
  expect(inventory).toHaveTextContent('13 lb.');
  expect(inventory).toHaveTextContent('Equipment: Armor');
});

test('submits the natural physical roll with the expected state version', async () => {
  const api = await setupPanel();

  fireEvent.change(screen.getByLabelText(/Physical d20 result/i), {
    target: { value: '14' },
  });
  fireEvent.click(screen.getByRole('button', { name: /Submit roll/i }));

  await waitFor(() => {
    expect(api.submitPhysicalRoll).toHaveBeenCalledWith(
      'session-one',
      'roll-7',
      {
        player_id: 'player-one',
        natural_roll: 14,
        expected_state_version: 42,
      },
    );
  });
  expect(await screen.findByText('State v43')).toBeInTheDocument();
});

test('shows a target only when the authoritative pending roll marks it public', async () => {
  const publicApi = createApi();
  publicApi.getGameState.mockResolvedValueOnce({
    ...gameState,
    pending_roll: {
      ...gameState.pending_roll,
      dc_visibility: 'public',
      target_total: 15,
    },
  });
  await setupPanel(publicApi);

  expect(screen.getByText('Target 15')).toBeInTheDocument();
});

test('does not reveal a private target even if a private payload contains one', async () => {
  const privateApi = createApi();
  privateApi.getGameState.mockResolvedValueOnce({
    ...gameState,
    pending_roll: {
      ...gameState.pending_roll,
      dc_visibility: 'private',
      target_total: 30,
    },
  });
  await setupPanel(privateApi);

  expect(screen.queryByText('Target 30')).not.toBeInTheDocument();
});

test('does not invent a target when a public pending roll omits it', async () => {
  const publicApi = createApi();
  publicApi.getGameState.mockResolvedValueOnce({
    ...gameState,
    pending_roll: {
      ...gameState.pending_roll,
      dc_visibility: 'public',
    },
  });
  await setupPanel(publicApi);

  expect(screen.queryByText(/^Target /)).not.toBeInTheDocument();
});

test('switches between two player character sheets', async () => {
  await setupPanel();

  expect(screen.getByRole('heading', { name: 'Aria' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('tab', { name: /Player Two/i }));

  expect(screen.getByRole('heading', { name: 'Bram' })).toBeInTheDocument();
  expect(screen.getByText('24 / 28')).toBeInTheDocument();
  selectSheetTab('Spells');
  expect(screen.getByText('No spell slots.')).toBeInTheDocument();
  expect(screen.queryByLabelText(/Physical d20 result/i)).not.toBeInTheDocument();
});

test('normalizes the authoritative backend character shape', async () => {
  const backendState = {
    state_version: 5,
    players: [
      {
        player_id: 'player-caster',
        display_name: 'Player One',
        character: {
          name: 'Mira',
          class_name: 'Wizard',
          level: 2,
          hp: 9,
          max_hp: 12,
          temp_hp: 2,
          armor_class: 13,
          abilities: { intelligence: 16 },
          saving_throws: { intelligence: 5 },
          skills: { arcana: 5 },
          hit_dice: { d6: { maximum: 2, current: 2 } },
          spell_slots: { 1: { maximum: 3, current: 1 } },
          class_resources: {},
          currency: { gp: 7 },
          conditions: [],
          inventory: [],
        },
      },
    ],
  };
  const api = {
    getGameState: jest.fn().mockResolvedValue(backendState),
    submitPhysicalRoll: jest.fn(),
  };

  await setupPanel(api);

  expect(screen.getByText('9 / 12')).toBeInTheDocument();
  expect(screen.getByText('Temp HP: 2')).toBeInTheDocument();
  expect(screen.getByText('2 / 2 d6')).toBeInTheDocument();
  selectSheetTab('Spells');
  expect(screen.getByText('2 used, 1 available')).toBeInTheDocument();
  selectSheetTab('Inventory');
  expect(screen.getByText('7 gp')).toBeInTheDocument();
});

test('refetches the full ledger after a mutation-only roll response', async () => {
  const resolvedState = { ...gameState, state_version: 43, pending_roll: null };
  const api = {
    getGameState: jest.fn()
      .mockResolvedValueOnce(gameState)
      .mockResolvedValueOnce(resolvedState),
    submitPhysicalRoll: jest.fn().mockResolvedValue({
      state_version: 43,
      roll_result: { roll_id: 'roll-7', natural_roll: 12, total: 17 },
    }),
  };
  const rollEvent = jest.fn();
  window.addEventListener('dmb:physical-roll-resolved', rollEvent);
  await setupPanel(api);

  fireEvent.change(screen.getByLabelText(/Physical d20 result/i), {
    target: { value: '12' },
  });
  fireEvent.click(screen.getByRole('button', { name: /Submit roll/i }));

  await waitFor(() => expect(api.getGameState).toHaveBeenCalledTimes(2));
  expect(screen.getByRole('heading', { name: 'Aria' })).toBeInTheDocument();
  expect(screen.queryByText('Physical roll needed')).not.toBeInTheDocument();
  expect(rollEvent).toHaveBeenCalledTimes(1);
  expect(rollEvent.mock.calls[0][0].detail).toEqual(expect.objectContaining({ natural_roll: 12 }));
  window.removeEventListener('dmb:physical-roll-resolved', rollEvent);
});

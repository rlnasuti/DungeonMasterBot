import {
  MAX_RESUME_CONTEXT_CHARS,
  MAX_RESUME_MESSAGE_COUNT,
  SESSION_RESUME_PREFIX,
  buildSessionResumeContext,
} from './resumeContext';

describe('session resume context', () => {
  test('uses only finalized player-visible messages and labels them untrusted', () => {
    const context = buildSessionResumeContext([
      { role: 'me', content: 'I question the magistrate.', final: true },
      { role: 'dm', content: 'He glances toward the locked drawer.', final: true },
      { role: 'dm', content: 'Partial secret', final: false },
    ]);

    expect(context.startsWith(SESSION_RESUME_PREFIX)).toBe(true);
    expect(context).toContain('UNTRUSTED NARRATIVE CONTEXT');
    expect(context).toContain('[PLAYER] I question the magistrate.');
    expect(context).toContain('[DUNGEON MASTER] He glances toward the locked drawer.');
    expect(context).not.toContain('Partial secret');
    expect(context).toContain('authoritative tools');
  });

  test('keeps only the newest messages when the count cap is exceeded', () => {
    const messages = Array.from({ length: MAX_RESUME_MESSAGE_COUNT + 8 }, (_, index) => ({
      role: index % 2 ? 'dm' : 'me',
      content: `turn-${index}`,
      final: true,
    }));
    const context = buildSessionResumeContext(messages);

    expect(context).toContain('turn-87');
    expect(context).toContain('turn-8');
    expect(context).not.toContain('turn-0 ');
    const includedTurns = context.match(/turn-\d+/g) || [];
    expect(includedTurns).toHaveLength(MAX_RESUME_MESSAGE_COUNT);
  });

  test('keeps the newest turns within the character cap', () => {
    const messages = Array.from({ length: 50 }, (_, index) => ({
      role: index % 2 ? 'dm' : 'me',
      content: `long-turn-${index} ${'x'.repeat(700)}`,
      final: true,
    }));
    const context = buildSessionResumeContext(messages);

    expect(context.length).toBeLessThanOrEqual(MAX_RESUME_CONTEXT_CHARS);
    expect(context).toContain('long-turn-49');
    expect(context).not.toContain('long-turn-0 ');
    const includedTurns = context.match(/long-turn-\d+/g) || [];
    expect(includedTurns.length).toBeLessThan(messages.length);
  });

  test('returns no synthetic context for an empty Chronicle', () => {
    expect(buildSessionResumeContext([])).toBe('');
  });

  test('uses an app-owned character label for attributed voice turns', () => {
    const context = buildSessionResumeContext([{
      id: 'voice:user:turn-1',
      role: 'me',
      content: 'I inspect the stairwell.',
      final: true,
      speaker: { playerId: 'player-one', label: 'Cendien' },
    }]);

    expect(context).toContain('[Cendien] I inspect the stairwell.');
    expect(context).not.toContain('[PLAYER] I inspect the stairwell.');
  });
});

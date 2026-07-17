import React from 'react';
import { render, screen } from '@testing-library/react';
import DungeonMasterPortrait from './DungeonMasterPortrait';

test('announces the active voice state', () => {
  const { container } = render(
    <DungeonMasterPortrait state="speaking" audioLevel={0.6} />
  );

  expect(screen.getByRole('status')).toHaveTextContent('Narrating');
  expect(screen.getByRole('heading', { name: 'Marin' })).toBeInTheDocument();
  expect(container.querySelector('.dm-presence')).toHaveStyle('--speech-level: 0.6');
  expect(container.querySelector('.dm-presence')).toHaveStyle('--mouth-y: 47.2%');
  expect(container.querySelectorAll('.dm-portrait-image')).toHaveLength(1);
  expect(container.querySelector('.dm-portrait-image')).toHaveAttribute(
    'src',
    '/assets/dungeon-master-portrait-marin.png',
  );
  expect(container.querySelector('.dm-mouth-opening')).toBeInTheDocument();
});

test('clamps invalid audio levels', () => {
  const { container } = render(
    <DungeonMasterPortrait state="listening" audioLevel={4} />
  );

  expect(container.querySelector('.dm-presence')).toHaveStyle('--speech-level: 1');
  expect(screen.getByRole('status')).toHaveTextContent('Listening to the party');
});

test('clamps negative and non-numeric audio levels to silence', () => {
  const { container, rerender } = render(
    <DungeonMasterPortrait state="idle" audioLevel={-2} />
  );

  expect(container.querySelector('.dm-presence')).toHaveStyle('--speech-level: 0');
  rerender(<DungeonMasterPortrait state="idle" audioLevel="not-a-number" />);
  expect(container.querySelector('.dm-presence')).toHaveStyle('--speech-level: 0');
});

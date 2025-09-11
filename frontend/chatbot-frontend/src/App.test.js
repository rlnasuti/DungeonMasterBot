import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

// Mock axios to avoid ESM import issues in Jest and real HTTP calls.
jest.mock('axios', () => ({
  post: jest.fn(() => Promise.resolve({ data: { response: 'The DM speaks.' } })),
}));

test('renders composer input', () => {
  render(<App />);
  expect(screen.getByLabelText(/message input/i)).toBeInTheDocument();
});

# DungeonMasterBot Frontend

This package contains the React interface for DungeonMasterBot. It was bootstrapped with Create React App, but the scripts below reflect the current stack.

## Prerequisites

- Node.js 18+ (or any version supported by `react-scripts`)
- npm 9+

## Install Dependencies

```bash
npm install
```

## Development Server

```bash
npm run dev
```

The app runs at [http://localhost:3000](http://localhost:3000). Axios requests target `http://localhost:8000/chat`, so make sure the Flask API is running on port 8000.

## Scripts

- `npm run dev`: start the React dev server with hot reload.
- `npm run build`: create a production bundle in `build/`.
- `npm test`: run the CRA test runner in watch mode.
- `npm run eject`: expose the underlying CRA configuration (irreversible).

## Environment

No frontend-specific environment variables are required. Update the axios base URL in `src/App.js` if your backend runs on a different host or port.

import logo from './logo.svg';
import './App.css';
import ChatComponent from './ChatComponent';

function App() { // This is the main parent component
  return (
      <div className="app-container">
          <div className="control-pane">
              {/* Place any controls or content for the control pane here */}
          </div>
          <ChatComponent />
      </div>
  );
}

export default App;

import { createRoot } from 'react-dom/client';
import App from './App';
import './style.css';
import '../design/tokens.css';

createRoot(document.getElementById('root')!).render(<App />);

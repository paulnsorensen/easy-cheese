import {useEffect, useState} from 'react';

const STORAGE_KEY = 'mold-review-theme';
const CHOICES = ['system', 'light', 'dark'];
const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');

function storedChoice() {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return CHOICES.includes(value) ? value : 'system';
  } catch {
    return 'system';
  }
}

// `choice` is what the user selected. `resolved` is the theme on screen.
export function useTheme() {
  const [choice, setChoice] = useState(storedChoice);
  const [systemDark, setSystemDark] = useState(darkQuery.matches);

  useEffect(() => {
    const listen = event => setSystemDark(event.matches);
    darkQuery.addEventListener('change', listen);
    return () => darkQuery.removeEventListener('change', listen);
  }, []);

  useEffect(() => {
    if (choice === 'system') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = choice;
    try {
      localStorage.setItem(STORAGE_KEY, choice);
    } catch {
      // Storage is optional. The choice stays for this page load.
    }
  }, [choice]);

  const resolved = choice === 'system' ? (systemDark ? 'dark' : 'light') : choice;
  return {choice, setChoice, resolved, choices: CHOICES};
}

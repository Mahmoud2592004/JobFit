const PATHS = {
  dash: 'M3 11l9-8 9 8v10h-6v-6H9v6H3z',
  jobs: 'M4 8h16v11H4zM9 8V5h6v3',
  res: 'M6 3h9l4 4v14H6zM9 12h7M9 16h7',
  track: 'M4 5h4v14H4zM10 5h4v9h-4zM16 5h4v6h-4z',
  bell: 'M6 17v-6a6 6 0 0112 0v6l2 2H4zM10 21h4',
  prof: 'M12 12a4 4 0 100-8 4 4 0 000 8zM4 21a8 8 0 0116 0',
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name }: { name: IconName }) {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  );
}

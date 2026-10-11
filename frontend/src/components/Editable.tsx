import { memo } from 'react';

interface BaseProps {
  /** Text the field is (re)initialised with. Changing `resetKey` remounts the field with this text. */
  initial: string;
  resetKey: number;
  onText: (text: string) => void;
  id?: string;
  className?: string;
  style?: React.CSSProperties;
  label: string;
}

const read = (el: HTMLElement) => (el.innerText ?? el.textContent ?? '').trim();

/**
 * Uncontrolled contentEditable block. We render `initial` once per `resetKey` and never
 * re-render children while the user types, so the caret never jumps.
 */
export const EditableText = memo(function EditableText({ initial, resetKey, onText, className = 'ed', ...rest }: BaseProps) {
  return (
    <div
      key={resetKey}
      className={className}
      id={rest.id}
      style={rest.style}
      aria-label={rest.label}
      contentEditable
      suppressContentEditableWarning
      onInput={(e) => onText(read(e.currentTarget))}
    >
      {initial}
    </div>
  );
});

export const EditableList = memo(function EditableList({ initial, resetKey, onText, className = 'ed', ...rest }: BaseProps) {
  const lines = initial.split('\n').filter(Boolean);
  return (
    <ul
      key={resetKey}
      className={className}
      id={rest.id}
      aria-label={rest.label}
      contentEditable
      suppressContentEditableWarning
      onInput={(e) =>
        onText(
          Array.from(e.currentTarget.querySelectorAll('li'))
            .map((li) => read(li))
            .filter(Boolean)
            .join('\n'),
        )
      }
    >
      {lines.map((l, i) => (
        <li key={i}>{l}</li>
      ))}
    </ul>
  );
});

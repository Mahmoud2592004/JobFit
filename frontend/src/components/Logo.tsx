import { Link } from 'react-router-dom';

export function Logo({ to = '/' }: { to?: string }) {
  return (
    <Link className="logo" to={to}>
      <b>JF</b>
      <span>JobFit</span>
    </Link>
  );
}

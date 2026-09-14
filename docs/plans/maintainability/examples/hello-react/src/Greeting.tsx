/** A named component and an arrow component, so both definition shapes appear. */

export function Greeting({ name }: { name: string }) {
  return <h1>Hello, {name}!</h1>;
}

export const Shout = ({ name }: { name: string }) => (
  <strong>{name.toUpperCase()}</strong>
);

/** Two uses of one component, and one use of the arrow component. */

import { Greeting, Shout } from "./Greeting";

export default function App() {
  return (
    <div>
      <Greeting name="world" />
      <Greeting name="again" />
      <Shout name="world" />
    </div>
  );
}

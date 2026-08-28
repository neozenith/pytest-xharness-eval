// The partial bundle ships no types; it is the same API surface as plotly.js.
declare module "plotly.js-basic-dist-min" {
  import * as Plotly from "plotly.js";
  export = Plotly;
}

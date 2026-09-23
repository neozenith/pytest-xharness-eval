import { n as styledExport, r as require_jsx_runtime, t as Text } from "./index-BmfwMReJ.js";
//#region src/components/ui/badge.tsx
/** The pill badge, built on Tamagui; `tone` colours it from the design tokens. */
/**
* Tone is carried by a tint plus ink of the same hue, never a solid slab: sixteen solid
* verdict pills stacked down a table column drown the data they annotate, and ink-on-tint
* clears AA in both themes for every semantic colour (solid `warn` did not).
*/
var tint = (token) => ({
	backgroundColor: `color-mix(in srgb, var(--xh-${token}) 13%, transparent)`,
	borderColor: `color-mix(in srgb, var(--xh-${token}) 32%, transparent)`,
	color: `var(--xh-${token})`
});
var Badge = styledExport(Text, {
	name: "XhBadge",
	render: "span",
	display: "inline-flex",
	alignItems: "center",
	justifyContent: "center",
	borderRadius: 999,
	borderWidth: 1,
	borderColor: "transparent",
	paddingHorizontal: 8,
	height: 20,
	fontSize: 11,
	lineHeight: 18,
	fontWeight: "600",
	letterSpacing: .3,
	whiteSpace: "nowrap",
	variants: { tone: {
		good: tint("good"),
		bad: tint("bad"),
		warn: tint("warn"),
		accent: tint("accent"),
		outline: {
			borderColor: "$line",
			color: "$muted",
			backgroundColor: "transparent"
		}
	} },
	defaultVariants: { tone: "outline" }
});
//#endregion
//#region src/components/VerdictBadge.tsx
var import_jsx_runtime = require_jsx_runtime();
var TOKEN = {
	pass: "good",
	fail: "bad"
};
/** The history verdict as a pill: pass, fail, or "no history" when the line never landed. */
function VerdictBadge({ verdict }) {
	const token = verdict ? TOKEN[verdict] ?? "warn" : null;
	const tone = token ?? "outline";
	const loud = token != null && verdict !== "pass";
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Badge, {
		tone,
		fontFamily: "$mono",
		textTransform: "uppercase",
		minWidth: 54,
		...loud ? {
			backgroundColor: `color-mix(in srgb, var(--xh-${token}) 20%, transparent)`,
			borderColor: `color-mix(in srgb, var(--xh-${token}) 58%, transparent)`,
			fontWeight: "700"
		} : null,
		children: verdict ?? "no history"
	});
}
//#endregion
export { VerdictBadge };

//# sourceMappingURL=VerdictBadge-DbV5yKO0.js.map
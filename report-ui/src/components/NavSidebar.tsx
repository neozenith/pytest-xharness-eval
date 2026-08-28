/**
 * The collapsible left navigation (glossary: `NavSidebar`): the sweep's hierarchy as a tree
 * — skill → suite → harness → model → one entry per session (its case) — plus section
 * jump-links for the open session. Every level starts collapsed; the reader opts into
 * expanding it, and the active session's ancestors open themselves so a deeplink is never
 * hidden. Collapse is a viewer preference, not a route param: it changes how you look,
 * never what you look at.
 */
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { Text, View, XStack } from "tamagui";
import { Button } from "@/components/ui/button";
import { El } from "@/components/El";
import { short } from "@/lib/format";
import { navigateOnClick, overviewSearch, sessionSearch, type Route } from "@/lib/route";
import type { Cell, Index } from "@/lib/types";

const STORAGE_KEY = "xharness-report-nav";

const initialCollapsed = (): boolean => {
  try {
    return localStorage.getItem(STORAGE_KEY) === "collapsed";
  } catch {
    return false;
  }
};

const rememberCollapsed = (collapsed: boolean): void => {
  try {
    localStorage.setItem(STORAGE_KEY, collapsed ? "collapsed" : "open");
  } catch {
    /* a remembered sidebar is a convenience, never a requirement */
  }
};

/** The open session's in-page sections; clicking scrolls, the hash (the route) stays untouched. */
const SECTIONS: [string, string][] = [
  ["SessionMetaTable", "Metadata"],
  ["TokenWaterfallChart", "Token waterfall"],
  ["ContextWindowChart", "Context window"],
  ["ReconciliationPanel", "Reconciliation"],
  ["CostByTierPanel", "Cost by tier"],
  ["SkillCoveragePanelWrap", "Skill coverage"],
  ["RecordKindsPanel", "Record kinds"],
  ["SessionTurnTablePanel", "Turns & records"],
  ["FinalMessagePanel", "Final message"],
];

function VerdictDot({ verdict }: { verdict: string | null }) {
  const tone = verdict === "pass" ? "var(--xh-good)" : verdict === "fail" ? "var(--xh-bad)" : verdict ? "var(--xh-warn)" : "var(--xh-line)";
  return (
    <span
      aria-hidden
      style={{ display: "inline-block", width: 8, height: 8, flexShrink: 0, borderRadius: 999, background: tone }}
      title={verdict ?? "no history"}
    />
  );
}

/** Group in first-seen order, so the tree follows the index. */
function groupBy(cells: Cell[], keyOf: (c: Cell) => string): Map<string, Cell[]> {
  const groups = new Map<string, Cell[]>();
  for (const cell of cells) {
    const key = keyOf(cell);
    const list = groups.get(key) ?? [];
    list.push(cell);
    groups.set(key, list);
  }
  return groups;
}

const suiteName = (c: Cell): string => (c.suite ? (c.suite.split("/").pop() ?? c.suite) : "(no suite)");

interface Props {
  index: Index | null;
  route: Route;
}

/** One collapsed-by-default tree level: a chevroned header the reader opts into opening. */
function Group({
  label,
  className,
  open,
  onToggle,
  count,
  children,
}: {
  label: string;
  className?: string;
  open: boolean;
  onToggle: () => void;
  count: number;
  children: ReactNode;
}) {
  return (
    <div className="nav-branch">
      <button type="button" className={`nav-group ${className ?? ""}`} onClick={onToggle} aria-expanded={open} title={label}>
        <ChevronRight className="chev" size={11} aria-hidden />
        <span className="truncate">{label}</span>
        <span className="count">{count}</span>
      </button>
      {open ? children : null}
    </div>
  );
}

export function NavSidebar({ index, route }: Props) {
  const [collapsed, setCollapsed] = useState(initialCollapsed);
  const activeSession = route.view === "session" ? route.sessionId : null;
  const theme = route.theme;

  // Explicit reader choices per tree path; a path with no choice falls back to its default:
  // closed, unless it is an ancestor of the active session.
  const [chosen, setChosen] = useState<Record<string, boolean>>({});
  const activePaths = useMemo(() => {
    const cell = index?.cells.find((c) => c.session_id === activeSession);
    if (!cell) return new Set<string>();
    const skill = cell.skill ?? "(no skill)";
    const suite = suiteName(cell);
    return new Set([skill, `${skill}/${suite}`, `${skill}/${suite}/${cell.harness}`, `${skill}/${suite}/${cell.harness}/${cell.model}`]);
  }, [index, activeSession]);
  const isOpen = (path: string): boolean => chosen[path] ?? activePaths.has(path);
  const toggleGroup = (path: string) => setChosen((prev) => ({ ...prev, [path]: !isOpen(path) }));

  const toggle = () => {
    setCollapsed((prev) => {
      rememberCollapsed(!prev);
      return !prev;
    });
  };

  const jump = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ block: "start", behavior: "smooth" });
  };

  return (
    <View
      render="aside"
      id="NavSidebar"
      data-el="NavSidebar"
      data-state={collapsed ? "collapsed" : "open"}
      flexShrink={0}
      width={collapsed ? 36 : 264}
      transition="200ms"
      overflow="hidden"
      // position via tamagui props: its atomic classes would beat a tailwind `sticky` class
      position="sticky"
      top={61}
      alignSelf="flex-start"
      height="calc(100vh - 61px)"
      borderRightWidth={1}
      borderRightColor="$line"
      borderStyle="solid"
    >
      <View height="100%" flexDirection="column">
        <XStack
          alignItems="center"
          paddingVertical={8}
          justifyContent={collapsed ? "center" : "space-between"}
          paddingLeft={collapsed ? 0 : 16}
          paddingRight={collapsed ? 0 : 8}
        >
          {collapsed ? null : (
            <Text color="$muted" fontFamily="$body" fontSize={12} fontWeight="600" letterSpacing={0.5} textTransform="uppercase">
              Navigate
              <El name="NavSidebar" />
            </Text>
          )}
          <Button
            id="NavToggle"
            variant="ghost"
            size="icon-sm"
            render={<button type="button" title={collapsed ? "expand navigation" : "collapse navigation"} />}
            aria-label={collapsed ? "expand navigation" : "collapse navigation"}
            aria-expanded={!collapsed}
            onClick={toggle}
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </Button>
        </XStack>
        {collapsed ? null : (
          <View
            render="nav"
            minHeight={0}
            flexGrow={1}
            flexShrink={1}
            flexBasis={0}
            paddingRight={8}
            paddingBottom={24}
            paddingLeft={12}
            style={{ overflowY: "auto" }}
          >
            <a
              href={overviewSearch(null, theme)}
              onClick={navigateOnClick(overviewSearch(null, theme))}
              className="nav-link"
              data-active={route.view === "overview" ? "true" : undefined}
            >
              Overview
            </a>
            {index
              ? [...groupBy(index.cells, (c) => c.skill ?? "(no skill)").entries()].map(([skill, ofSkill]) => (
                  <div key={skill} style={{ marginTop: 8 }}>
                    <Group label={skill} count={ofSkill.length} open={isOpen(skill)} onToggle={() => toggleGroup(skill)}>
                      {[...groupBy(ofSkill, suiteName).entries()].map(([suite, ofSuite]) => (
                        <div key={suite} style={{ marginTop: 4, paddingLeft: 10 }}>
                          <Group
                            label={suite}
                            className="mono"
                            count={ofSuite.length}
                            open={isOpen(`${skill}/${suite}`)}
                            onToggle={() => toggleGroup(`${skill}/${suite}`)}
                          >
                            {[...groupBy(ofSuite, (c) => c.harness).entries()].map(([harness, ofHarness]) => (
                              <div key={harness} style={{ paddingLeft: 10 }}>
                                <Group
                                  label={harness}
                                  count={ofHarness.length}
                                  open={isOpen(`${skill}/${suite}/${harness}`)}
                                  onToggle={() => toggleGroup(`${skill}/${suite}/${harness}`)}
                                >
                                  {[...groupBy(ofHarness, (c) => c.model).entries()].map(([model, ofModel]) => (
                                    <div key={model} style={{ paddingLeft: 10 }}>
                                      <Group
                                        label={model}
                                        className="mono"
                                        count={ofModel.length}
                                        open={isOpen(`${skill}/${suite}/${harness}/${model}`)}
                                        onToggle={() => toggleGroup(`${skill}/${suite}/${harness}/${model}`)}
                                      >
                                        {ofModel.map((cell) => {
                                          const active = cell.session_id === activeSession;
                                          return (
                                            <div key={cell.session_id} style={{ paddingLeft: 4 }}>
                                              <a
                                                href={sessionSearch(cell.session_id, null, null, { theme })}
                                                onClick={navigateOnClick(sessionSearch(cell.session_id, null, null, { theme }))}
                                                className="nav-link"
                                                data-active={active ? "true" : undefined}
                                                title={`${cell.skill ? `${cell.skill} · ` : ""}${cell.case} · ${cell.harness}/${cell.model} · ${cell.session_id}`}
                                              >
                                                <VerdictDot verdict={cell.verdict} />
                                                <span className="truncate">{cell.case}</span>
                                                <code className="sid">{short(cell.session_id)}</code>
                                              </a>
                                              {active ? (
                                                <ul
                                                  style={{ margin: 0, marginLeft: 12, padding: 0, listStyle: "none", borderLeft: "1px solid var(--xh-line)" }}
                                                >
                                                  {SECTIONS.map(([id, label]) => (
                                                    <li key={id}>
                                                      <button type="button" onClick={() => jump(id)} className="nav-section">
                                                        {label}
                                                      </button>
                                                    </li>
                                                  ))}
                                                </ul>
                                              ) : null}
                                            </div>
                                          );
                                        })}
                                      </Group>
                                    </div>
                                  ))}
                                </Group>
                              </div>
                            ))}
                          </Group>
                        </div>
                      ))}
                    </Group>
                  </div>
                ))
              : null}
          </View>
        )}
      </View>
    </View>
  );
}

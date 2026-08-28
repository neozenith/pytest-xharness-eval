import { useState } from "react";
import { Text, XStack } from "tamagui";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { El } from "@/components/El";
import { fmt } from "@/lib/format";
import { Chip, Notice } from "./shared";

export interface CoverageFile {
  path: string;
  kind: string;
  bytes: number;
  sha256?: string;
  ignored: boolean;
  loaded: number[];
  run: number[];
}

export interface SkillCoverage {
  skill?: string;
  files?: CoverageFile[];
  loaded?: string[];
  run?: string[];
  not_loaded?: string[];
  not_run?: string[];
  summary?: {
    files?: number;
    ignored?: number;
    docs?: number;
    scripts?: number;
    tests?: number;
    assets?: number;
    loaded?: number;
    run?: number;
  };
}

type Filter = "all" | "loaded" | "run" | "not_loaded" | "not_run" | "ignored";

const FILTERS: Record<Filter, (f: CoverageFile, showIgnored: boolean) => boolean> = {
  all: (f, showIgnored) => showIgnored || !f.ignored,
  loaded: (f) => !f.ignored && (f.loaded.length > 0 || f.run.length > 0),
  run: (f) => !f.ignored && f.run.length > 0,
  not_loaded: (f) => !f.ignored && !f.loaded.length && !f.run.length,
  not_run: (f) => !f.ignored && f.kind === "script" && !f.run.length,
  ignored: (f) => f.ignored,
};

const Turns = ({ list }: { list: number[] }) =>
  list.length ? (
    <>
      {list.map((n) => (
        <code key={n} className="code-chip">
          t{n}
        </code>
      ))}
    </>
  ) : null;

function status(f: CoverageFile) {
  if (f.ignored) return <span className="muted">ignored</span>;
  if (f.run.length) return <span className="accentc">run</span>;
  if (f.loaded.length) return <span className="good">loaded</span>;
  if (f.kind === "script") return <span className="bad">not run · not loaded</span>;
  if (f.kind === "test") return <span className="muted">test (not expected)</span>;
  return <span className="bad">not loaded</span>;
}

/**
 * The skill's files as catalogued at collection (ignore rules applied) and the turns that
 * loaded or ran each (ADR 0022, 0023). The summary chips filter the table; `ShowIgnored`
 * reveals the files the ignore rules removed.
 */
export function SkillCoveragePanel({ coverage }: { coverage: SkillCoverage | null | undefined }) {
  const [filter, setFilter] = useState<Filter>("all");
  const [showIgnored, setShowIgnored] = useState(false);
  const cov = coverage ?? {};
  const rows = cov.files ?? [];
  const s = cov.summary ?? {};
  const pick = (f: Filter) => setFilter(filter === f && f !== "all" ? "all" : f);
  const chip = (label: string, value: React.ReactNode, f?: Filter) =>
    f ? (
      <Chip key={label} label={label} on={filter === f} onClick={() => pick(f)}>
        {value}
      </Chip>
    ) : (
      <Chip key={label} label={label}>
        {value}
      </Chip>
    );
  const visible = rows.filter((f) => FILTERS[filter](f, showIgnored));
  return (
    <Card id="SkillCoveragePanelWrap" data-el="SkillCoveragePanel">
      <CardHeader>
        <CardTitle>
          Skill coverage
          <El name="SkillCoveragePanel" />
        </CardTitle>
        <CardDescription>
          The skill's files as catalogued at collection (ignore rules applied), and the turns that loaded or ran each. Files never touched are the decision
          paths this run did not take.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <XStack id="SkillCoverageSummary" data-el="SkillCoverageSummary" flexWrap="wrap" gap={8} marginBottom={12}>
          {rows.length ? (
            [
              chip("skill", <code>{cov.skill}</code>),
              chip("files", fmt(s.files), "all"),
              chip("docs", fmt(s.docs)),
              chip("scripts", fmt(s.scripts)),
              chip("tests", fmt(s.tests)),
              chip("assets", fmt(s.assets)),
              chip(
                "loaded",
                <>
                  <span className="good">{fmt(s.loaded)}</span> / {fmt(s.files)}
                </>,
                "loaded",
              ),
              chip(
                "run",
                <>
                  <span className="accentc">{fmt(s.run)}</span> / {fmt(s.scripts)} scripts
                </>,
                "run",
              ),
              chip("not_loaded", <span className="bad">{fmt((cov.not_loaded ?? []).length)}</span>, "not_loaded"),
              chip("not_run", <span className="bad">{fmt((cov.not_run ?? []).length)}</span>, "not_run"),
              chip("ignored", fmt(s.ignored), "ignored"),
            ]
          ) : (
            <Notice>no skill coverage on this result (predates ADR 0022); re-run or replay the cell</Notice>
          )}
        </XStack>
        <XStack render={<label />} alignItems="center" gap={8} marginBottom={12}>
          <Switch id="ShowIgnored" checked={showIgnored} onCheckedChange={setShowIgnored} aria-label="show ignored files" />
          <Text color="$muted" fontSize={14} fontFamily="$body">
            show ignored files
          </Text>
        </XStack>
        <Table id="SkillCoveragePanel">
          <TableHeader>
            <TableRow>
              <TableHead>path</TableHead>
              <TableHead>kind</TableHead>
              <TableHead className="num">bytes</TableHead>
              <TableHead>loaded at turns</TableHead>
              <TableHead>run at turns</TableHead>
              <TableHead>status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {visible.map((f) => (
              <TableRow key={f.path} className={f.ignored ? "muted" : undefined}>
                <TableCell>
                  <code>{f.path}</code>
                </TableCell>
                <TableCell>{f.kind}</TableCell>
                <TableCell className="num">{fmt(f.bytes)}</TableCell>
                <TableCell>
                  <Turns list={f.loaded} />
                </TableCell>
                <TableCell>
                  <Turns list={f.run} />
                </TableCell>
                <TableCell>{status(f)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

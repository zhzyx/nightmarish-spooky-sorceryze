import type { SVGProps } from "react";

export type IconName =
  | "home"
  | "docs"
  | "issues"
  | "repos"
  | "requirements"
  | "settings"
  | "search"
  | "sparkles"
  | "arrowUp"
  | "arrowRight"
  | "arrowLeft"
  | "plus"
  | "bell"
  | "chevronDown"
  | "chevronRight"
  | "branch"
  | "clock"
  | "check"
  | "menu"
  | "close"
  | "file"
  | "folder"
  | "more"
  | "filter"
  | "grid"
  | "list"
  | "comment"
  | "paperclip"
  | "lock"
  | "command"
  | "users"
  | "alert"
  | "eye"
  | "pen"
  | "history"
  | "link"
  | "code"
  | "download"
  | "gitCommit"
  | "pullRequest"
  | "layers"
  | "cloud"
  | "shield"
  | "checkCircle"
  | "circle"
  | "copy";

const iconPaths: Record<IconName, string[]> = {
  home: ["M3.5 10.5 12 3l8.5 7.5", "M5.5 9.5V21h13V9.5", "M9.5 21v-6h5v6"],
  docs: ["M6 3.5h8l4 4v13H6z", "M14 3.5v5h4", "M9 12h6", "M9 16h4"],
  issues: ["M5 4.5h14v16H5z", "M8 2.5v4", "M16 2.5v4", "M8 11h5", "M8 15h8"],
  repos: ["M5 4v15", "M5 8h6a4 4 0 0 1 4 4v7", "M8 2 5 5l3 3", "M15 15l-3 3 3 3"],
  requirements: [
    "M6 3.5h12v17H6z",
    "M9 8h6",
    "M9 12h6",
    "M9 16h3",
    "M4 6h2v12H4",
  ],
  settings: [
    "M4 7h5",
    "M13 7h7",
    "M4 17h7",
    "M15 17h5",
    "M11 4.5v5",
    "M13 14.5v5",
  ],
  search: ["M10.8 4a6.8 6.8 0 1 0 0 13.6 6.8 6.8 0 0 0 0-13.6z", "M16 16l4.5 4.5"],
  sparkles: [
    "M12 3l1.6 5.4L19 10l-5.4 1.6L12 17l-1.6-5.4L5 10l5.4-1.6L12 3z",
    "M18.5 3v3",
    "M17 4.5h3",
    "M5.5 17v2.5",
    "M4.2 18.2h2.6",
  ],
  arrowUp: ["M12 20V4", "M5.5 10.5 12 4l6.5 6.5"],
  arrowRight: ["M4 12h16", "M14 6l6 6-6 6"],
  arrowLeft: ["M20 12H4", "M10 6l-6 6 6 6"],
  plus: ["M12 5v14", "M5 12h14"],
  bell: ["M6 9a6 6 0 0 1 12 0c0 5 2 5.5 2 7H4c0-1.5 2-2 2-7z", "M10 20h4"],
  chevronDown: ["M6 9l6 6 6-6"],
  chevronRight: ["M9 6l6 6-6 6"],
  branch: ["M6 3.5v17", "M6 8h7a4 4 0 0 1 4 4v8.5", "M15.5 6.5h1", "M4.5 4.5h3", "M16 8.5h1"],
  clock: ["M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17z", "M12 7.5V12l3 2"],
  check: ["M5 12.5l4.5 4.5L19 6.5"],
  menu: ["M4 7h16", "M4 12h16", "M4 17h16"],
  close: ["M6 6l12 12", "M18 6 6 18"],
  file: ["M6 3.5h8l4 4v13H6z", "M14 3.5v5h4"],
  folder: ["M3.5 6.5h6l2 2h9v11h-17z"],
  more: [
    "M6 12h.01",
    "M12 12h.01",
    "M18 12h.01",
  ],
  filter: ["M4 5h16l-6.3 7.2V20l-3.4-2v-5.8z"],
  grid: ["M4 4h6v6H4z", "M14 4h6v6h-6z", "M4 14h6v6H4z", "M14 14h6v6h-6z"],
  list: ["M9 6h11", "M9 12h11", "M9 18h11", "M4.5 6h.01", "M4.5 12h.01", "M4.5 18h.01"],
  comment: ["M4.5 5h15v11h-9l-4 3v-3h-2z"],
  paperclip: [
    "M9 12.5l5.7-5.7a3.4 3.4 0 0 1 4.8 4.8l-7.4 7.4a5.6 5.6 0 0 1-7.9-7.9l7-7",
  ],
  lock: ["M6.5 10.5h11v10h-11z", "M9 10.5V8a3 3 0 0 1 6 0v2.5"],
  command: [
    "M9 6.5A2.5 2.5 0 1 0 6.5 9H9z",
    "M15 6.5A2.5 2.5 0 1 1 17.5 9H15z",
    "M9 17.5A2.5 2.5 0 1 1 6.5 15H9z",
    "M15 17.5A2.5 2.5 0 1 0 17.5 15H15z",
    "M9 6.5v11",
    "M15 6.5v11",
    "M6.5 9h11",
    "M6.5 15h11",
  ],
  users: [
    "M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z",
    "M2.8 20c.4-4 2.5-6 6.2-6s5.8 2 6.2 6",
    "M16 4.8a3 3 0 0 1 0 5.8",
    "M17.5 14.3c2.1.6 3.4 2.5 3.7 5.7",
  ],
  alert: ["M12 3.5 22 20H2z", "M12 9v5", "M12 17.5h.01"],
  eye: ["M2.5 12S6 6 12 6s9.5 6 9.5 6S18 18 12 18 2.5 12 2.5 12z", "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"],
  pen: ["M4 20l4.2-1 10.6-10.6-3.2-3.2L5 15.8z", "M13.7 6.5l3.2 3.2", "M4 20h5"],
  history: ["M3.5 8.5V4", "M3.5 8.5h4.5", "M4 9a8.5 8.5 0 1 1 .6 8", "M12 7.5V12l3 2"],
  link: [
    "M9.5 14.5l5-5",
    "M7 17a4.2 4.2 0 0 1 0-6l2-2",
    "M17 7a4.2 4.2 0 0 1 0 6l-2 2",
  ],
  code: ["M8.5 8 4 12l4.5 4", "M15.5 8l4.5 4-4.5 4", "M13 4l-2 16"],
  download: ["M12 3v12", "M7 10l5 5 5-5", "M4 20h16"],
  gitCommit: ["M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z", "M2.5 12H8", "M16 12h5.5"],
  pullRequest: [
    "M6 3.5v10",
    "M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    "M6 7a3 3 0 1 0 0-4 3 3 0 0 0 0 4z",
    "M18 9v8.5",
    "M18 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    "M9 6h4a5 5 0 0 1 5 3",
  ],
  layers: ["M12 3.5 21 8l-9 4.5L3 8z", "M3 12.5l9 4.5 9-4.5", "M3 16.8l9 4.5 9-4.5"],
  cloud: [
    "M6.5 18.5a4 4 0 0 1-.3-8 5.5 5.5 0 0 1 10.5-1 4.4 4.4 0 0 1 1.3 9z",
  ],
  shield: ["M12 3 20 6v5.2c0 4.8-3.4 8.3-8 9.8-4.6-1.5-8-5-8-9.8V6z", "M9 12l2 2 4-4"],
  checkCircle: ["M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17z", "M8 12.5l2.7 2.7L16.5 9"],
  circle: ["M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16z"],
  copy: ["M8 8h11v12H8z", "M5 16H3.5V4H15v1.5"],
};

export interface IconProps extends SVGProps<SVGSVGElement> {
  name: IconName;
  size?: number;
}

export function Icon({ name, size = 18, ...rest }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      height={size}
      viewBox="0 0 24 24"
      width={size}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={1.7}
      {...rest}
    >
      {iconPaths[name].map((path, index) => (
        <path d={path} key={`${name}-${index}`} />
      ))}
    </svg>
  );
}

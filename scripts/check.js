import { readdirSync } from "node:fs";
import { execFileSync } from "node:child_process";

for (const directory of ["src", "scripts", "tests"]) {
  for (const filename of readdirSync(directory).filter((name) =>
    name.endsWith(".js"),
  )) {
    execFileSync(process.execPath, ["--check", `${directory}/${filename}`], {
      stdio: "inherit",
    });
  }
}
console.log("JavaScript syntax checks passed.");

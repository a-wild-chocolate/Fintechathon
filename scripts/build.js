import { cp, mkdir } from "node:fs/promises";

await mkdir("dist", { recursive: true });
for (const path of ["index.html", "src", "demo"]) {
  await cp(path, `dist/${path}`, { recursive: true });
}
console.log("TradeX built into dist/");

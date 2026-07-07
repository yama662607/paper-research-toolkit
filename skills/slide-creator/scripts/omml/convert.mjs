// MathML (stdin) -> OMML (stdout). Used by add_equation.py.
// Setup once: bun install (in this directory).
import { mml2omml } from "mathml2omml";

const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const mathml = Buffer.concat(chunks).toString("utf8").trim();
if (!mathml) {
  console.error("convert.mjs: empty MathML input on stdin");
  process.exit(2);
}
try {
  process.stdout.write(mml2omml(mathml));
} catch (err) {
  console.error(`convert.mjs: conversion failed: ${err.message}`);
  process.exit(1);
}

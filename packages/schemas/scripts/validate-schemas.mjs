#!/usr/bin/env node
/**
 * Validates the Limes Axis JSON Schema package.
 *
 * Default mode (`pnpm test`): compiles every *.schema.json file with Ajv in
 * strict mode against the JSON Schema draft 2020-12 dialect, so structurally
 * broken or non-strict schemas fail the package test gate.
 *
 * Lint mode (`pnpm lint`, `--lint`): checks public-contract conventions:
 * canonical 2-space JSON formatting with a trailing newline, the draft
 * 2020-12 `$schema` marker, a stable `$id` under the schemas.limeslabs.eu
 * namespace that matches the file name, and a human-readable `title`.
 */

import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const PACKAGE_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema";
const ID_PREFIX = "https://schemas.limeslabs.eu/axis/";

const lintMode = process.argv.includes("--lint");

const schemaFiles = readdirSync(PACKAGE_ROOT)
  .filter((name) => name.endsWith(".schema.json"))
  .sort();

if (schemaFiles.length === 0) {
  console.error("No *.schema.json files found in packages/schemas.");
  process.exit(1);
}

const errors = [];

function lintSchema(fileName, rawText, schema) {
  const canonical = `${JSON.stringify(schema, null, 2)}\n`;
  if (rawText !== canonical) {
    errors.push(
      `${fileName}: not canonically formatted (expected 2-space indented JSON with a trailing newline).`,
    );
  }
  if (schema.$schema !== SCHEMA_DIALECT) {
    errors.push(`${fileName}: $schema must be ${SCHEMA_DIALECT}.`);
  }
  if (schema.$id !== `${ID_PREFIX}${fileName}`) {
    errors.push(`${fileName}: $id must be ${ID_PREFIX}${fileName}.`);
  }
  if (typeof schema.title !== "string" || schema.title.length === 0) {
    errors.push(`${fileName}: missing a non-empty title.`);
  }
}

function compileSchemas(schemas) {
  const ajv = new Ajv2020.default({ strict: true, allErrors: true });
  addFormats.default(ajv);
  for (const [fileName, schema] of schemas) {
    try {
      ajv.compile(schema);
    } catch (error) {
      errors.push(`${fileName}: failed to compile: ${error.message}`);
    }
  }
}

const parsedSchemas = [];
for (const fileName of schemaFiles) {
  const rawText = readFileSync(join(PACKAGE_ROOT, fileName), "utf8");
  let schema;
  try {
    schema = JSON.parse(rawText);
  } catch (error) {
    errors.push(`${fileName}: invalid JSON: ${error.message}`);
    continue;
  }
  parsedSchemas.push([fileName, schema]);
  if (lintMode) {
    lintSchema(fileName, rawText, schema);
  }
}

if (!lintMode) {
  compileSchemas(parsedSchemas);
}

if (errors.length > 0) {
  for (const message of errors) {
    console.error(`FAIL ${message}`);
  }
  process.exit(1);
}

const mode = lintMode ? "lint" : "compile";
for (const fileName of schemaFiles) {
  console.log(`ok ${mode} ${fileName}`);
}

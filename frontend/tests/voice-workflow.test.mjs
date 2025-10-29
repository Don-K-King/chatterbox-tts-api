import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

const componentPath = path.resolve('src/components/voices/VoiceWorkflowGuide.tsx');
const docPath = path.resolve('..', 'docs', 'VOICE_LIBRARY_MANAGEMENT.md');

const componentSource = await readFile(componentPath, 'utf8');
const documentation = await readFile(docPath, 'utf8');

test('VoiceWorkflowGuide highlights multilingual workflow steps', () => {
  assert.ok(componentSource.includes('USE_MULTILINGUAL_MODEL=true'), 'should mention USE_MULTILINGUAL_MODEL');
  assert.ok(componentSource.includes('VOICE_LIBRARY_DIR'), 'should guide directory preparation');
  assert.ok(componentSource.includes('curl -X POST http://localhost:4123/v1/voices'), 'should embed curl example');
  assert.ok(componentSource.includes('GET /v1/voices'), 'should remind to verify voices');
  assert.ok(componentSource.includes('voice_name=de_maria'), 'should suggest descriptive naming');
});

test('Voice management docs include PowerShell workflow', () => {
  assert.ok(documentation.includes('Voices versionieren (PowerShell Workflow)'), 'PowerShell section missing');
  assert.ok(documentation.includes('git status voices'), 'git status instruction missing');
  assert.ok(documentation.includes('git add voices'), 'git add instruction missing');
  assert.ok(documentation.includes('git push origin'), 'git push instruction missing');
});

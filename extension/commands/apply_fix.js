// extension/commands/apply_fix.js
// Handles the 'aviexa.applyFix' VS Code command.
// Receives a CodeFix payload, shows a diff, and applies via WorkspaceEdit on confirm.

'use strict';

const vscode = require('vscode');
const path = require('path');

/**
 * Register the aviexa.applyFix command.
 *
 * @param {vscode.ExtensionContext} ctx
 * @param {{ state: Object }} shared
 */
function register(ctx, shared) {
  return vscode.commands.registerCommand('aviexa.applyFix', async (fix) => {
    if (!fix || !fix.file_path) {
      vscode.window.showErrorMessage('Aviexa: No fix payload provided.');
      return;
    }

    try {
      // Resolve the file path relative to the workspace root
      const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri;
      if (!workspaceRoot) {
        vscode.window.showErrorMessage('Aviexa: No workspace folder open.');
        return;
      }

      const fileUri = vscode.Uri.joinPath(workspaceRoot, fix.file_path);

      // Open the document to verify it exists
      let document;
      try {
        document = await vscode.workspace.openTextDocument(fileUri);
      } catch (_) {
        vscode.window.showErrorMessage(
          `Aviexa: Cannot open file "${fix.file_path}". Does it exist in the workspace?`
        );
        return;
      }

      // Show the diff viewer so the user can review before applying
      const originalUri = fileUri.with({ scheme: 'aviexa-original' });
      // VS Code's diff command: vscode.diff takes two URIs
      await vscode.commands.executeCommand(
        'vscode.diff',
        originalUri,
        fileUri,
        `Aviexa Fix: ${path.basename(fix.file_path)}`
      );

      // Ask for confirmation
      const answer = await vscode.window.showInformationMessage(
        `Apply Bob's fix to ${fix.file_path} (lines ${fix.start_line}–${fix.end_line})?`,
        { modal: false },
        'Apply',
        'Skip'
      );

      if (answer !== 'Apply') return;

      // Apply via WorkspaceEdit
      const edit = new vscode.WorkspaceEdit();

      // Convert 1-based line numbers to 0-based Range
      const startLine = Math.max(0, (fix.start_line || 1) - 1);
      const endLine = Math.max(startLine, (fix.end_line || fix.start_line || 1) - 1);
      const endChar = document.lineAt(Math.min(endLine, document.lineCount - 1)).text.length;

      const range = new vscode.Range(
        new vscode.Position(startLine, 0),
        new vscode.Position(Math.min(endLine, document.lineCount - 1), endChar)
      );

      edit.replace(fileUri, range, fix.replacement_code || '');
      const success = await vscode.workspace.applyEdit(edit);

      if (success) {
        // Log to session store via state (best-effort)
        shared.state.appliedFixes = (shared.state.appliedFixes || 0) + 1;

        // Record applied fix to API if session is active
        if (shared.state.sessionId && shared.state.apiUrl) {
          try {
            const response = await fetch(
              `${shared.state.apiUrl}/session/${shared.state.sessionId}/fixes/applied`,
              {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  anomaly_id: fix.anomaly_id || null,
                  diagnosis_id: fix.diagnosis_id || null,
                  file_path: fix.file_path,
                  start_line: fix.start_line,
                  end_line: fix.end_line,
                  original_code: fix.original_code || null,
                  replacement_code: fix.replacement_code,
                  explanation: fix.explanation || 'Fix applied via VS Code extension',
                  risk_level: fix.risk_level || 'medium',
                  status: 'applied',
                  metadata: {}
                })
              }
            );
            
            if (response.ok) {
              console.log('Aviexa: Applied fix recorded to API');
            }
          } catch (err) {
            // Don't fail the apply operation if recording fails
            console.warn('Aviexa: Failed to record applied fix to API:', err.message);
          }
        }

        vscode.window.showInformationMessage(
          `✅ Fix applied to ${fix.file_path}:${fix.start_line}. ${fix.explanation || ''}`
        );
      } else {
        vscode.window.showErrorMessage('Aviexa: WorkspaceEdit failed — fix not applied.');
      }

    } catch (err) {
      vscode.window.showErrorMessage(`Aviexa: Error applying fix — ${err.message}`);
    }
  });
}

module.exports = { register };

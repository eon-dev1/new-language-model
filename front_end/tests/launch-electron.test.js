// Tests for sandboxFixCommands(): decides whether to print the chrome-sandbox fix.

'use strict';

const { sandboxFixCommands } = require('../scripts/launch-electron.js');

const SANDBOX = '/x/node_modules/electron/dist/chrome-sandbox';

describe('sandboxFixCommands()', () => {
  it('returns null when root-owned with mode 4755', () => {
    expect(sandboxFixCommands(SANDBOX, { uid: 0, mode: 0o104755 })).toBeNull();
  });

  it('returns chown and chmod when owned by a regular user', () => {
    expect(sandboxFixCommands(SANDBOX, { uid: 1000, mode: 0o104755 })).toEqual([
      `sudo chown root:root ${SANDBOX}`,
      `sudo chmod 4755 ${SANDBOX}`,
    ]);
  });

  it('returns the commands when root-owned but setuid bit is missing', () => {
    expect(sandboxFixCommands(SANDBOX, { uid: 0, mode: 0o100755 })).not.toBeNull();
  });
});

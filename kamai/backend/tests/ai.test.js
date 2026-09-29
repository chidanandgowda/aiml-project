const test = require('node:test')
const assert = require('node:assert/strict')

test('Node runtime provides fetch for the ML proxy', () => {
  assert.equal(typeof fetch, 'function')
})


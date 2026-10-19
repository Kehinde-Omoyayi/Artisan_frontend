const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');

require(path.join(__dirname, '../../static/js/api-errors.js'));
const apiErrors = global.ArtisanApiErrors;

test('combines a message and field details without repeating the same text', () => {
  assert.equal(
    apiErrors.format({
      message: 'Please review the form.',
      details: {
        phone_number: ['Enter a valid phone number.'],
        state: ['Choose a state.'],
        area: ['Please review the form.'],
      },
      code: 'INVALID',
      request_id: 'private-id',
    }, 400),
    'Please review the form. · Phone number: Enter a valid phone number. · State: Choose a state.'
  );
});

test('combines message, detail, and field errors while removing duplicates', () => {
  assert.equal(
    apiErrors.format({
      message: 'We could not save the request.',
      detail: 'Please check the highlighted fields.',
      error: 'Please check the highlighted fields.',
      details: { country: ['Choose a country.'] },
    }, 400),
    'We could not save the request. · Please check the highlighted fields. · Country: Choose a country.'
  );
});

test('handles string, object, and list details', () => {
  assert.equal(
    apiErrors.format({ detail: 'Access denied.', details: ['Profile incomplete.', { field: 'country', message: 'Choose a country.' }] }, 403),
    'Access denied. · Profile incomplete. · Country: Choose a country.'
  );
  assert.equal(apiErrors.format(['First issue.', 'Second issue.'], 400), 'First issue. · Second issue.');
  assert.equal(
    apiErrors.format({ message: 'Complete your profile.', details: { profile_role: 'customer', missing_fields: ['first_name', 'phone_number'] } }, 403),
    'Complete your profile. · Missing fields: First name, Phone number'
  );
});

test('falls back safely for network, server, and malformed response failures', async () => {
  assert.match(apiErrors.format(null, null, { networkError: true }), /couldn’t connect/);
  assert.match(apiErrors.format({ detail: 'Traceback (most recent call last): File "private.py"' }, 500), /temporarily unavailable/);
  const malformed = await apiErrors.readResponse({
    headers: { get: () => 'application/json' },
    json: () => Promise.reject(new SyntaxError('private body')),
  });
  assert.equal(malformed, null);
  assert.match(apiErrors.format(malformed, 502), /temporarily unavailable/);
});

test('does not expose a machine code used as the message', () => {
  const message = apiErrors.format({ message: 'PROFILE_INCOMPLETE' }, 403);
  assert.match(message, /permission/i);
  assert.doesNotMatch(message, /PROFILE_INCOMPLETE/);
});

test('does not expose codes, request IDs, traces, or HTML', () => {
  const message = apiErrors.format({
    message: '<html>proxy failure</html>',
    code: 'PROFILE_INCOMPLETE',
    request_id: 'private-request',
    traceback: 'Traceback secret',
  }, 500);
  assert.match(message, /temporarily unavailable/);
  assert.doesNotMatch(message, /PROFILE_INCOMPLETE|private-request|Traceback|proxy failure/i);
});

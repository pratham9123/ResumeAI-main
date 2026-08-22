const TARGET_ROLES = Object.freeze([
  'software_engineer',
  'backend_developer',
  'frontend_developer',
  'fullstack_developer',
  'data_analyst',
  'machine_learning_engineer',
]);

const TARGET_ROLE_SET = new Set(TARGET_ROLES);

function normalizeTargetRole(value) {
  if (value === undefined || value === null || value === '') return null;
  if (typeof value !== 'string') return null;
  const normalized = value.trim().toLowerCase();
  return TARGET_ROLE_SET.has(normalized) ? normalized : null;
}

module.exports = { TARGET_ROLES, TARGET_ROLE_SET, normalizeTargetRole };

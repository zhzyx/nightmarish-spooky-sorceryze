export function followUpTracking(config) {
  const authority = config.issue_tracking.authority_ref;
  if (typeof authority !== 'string' || !authority.trim()) throw Error('Git Issue handoff requires provider and authority reference');
  return {
    issueAction: 'Find or create linked Issue through the bound git-issue integration; verify authority and read back before marking linked',
    tracking: 'git-issue'
  };
}

export function deliveryAction() {
  return 'Verify bound Git Issue/release status and read back any authorized transition';
}

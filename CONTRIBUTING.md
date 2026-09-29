# Contributing to the Research Management System (RMS)

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Who Can Contribute

This project welcomes contributions from:

- **Researchers** exploring new fields with AI.
- **AI Engineers** building agentic research workflows.
- **Data Scientists** benchmarking new models.
- **Anyone** interested in the "Lineage of Ideas" and structured discovery.

## Ways to Contribute

### 1. Report Issues

- Bug reports for agents or research templates.
- Suggestions for improved research principles.
- Documentation clarifications.

### 2. Improve Agents

- Enhanced research protocols for Discovery, Specialist, or Worker roles.
- New agent capabilities for academic source integration.
- Bug fixes in existing agents.

### 3. Add Templates

- New templates for different research outputs (e.g., posters, presentations).
- Improved arXiv or Blog templates.
- Example Hypothesis DAGs for different domains.

### 4. Improve Documentation

- Clearer explanations of RMS principles.
- Integration guides for different AI tools.
- Case studies of successful AI-assisted research.

---

## Open source, and giving improvements back

These skills are open source: documentation under CC BY 4.0 and code under Apache-2.0 (see `LICENSE`). You may use, copy and adapt them, inside an organisation or out, on the terms of those licences.

If you improve a skill and the improvement would be useful to others beyond you or your organisation, please give it back to the source repository, [ai-assisted-research](https://github.com/dermot-obrien/ai-assisted-research): open an [issue](https://github.com/dermot-obrien/ai-assisted-research/issues) describing the improvement, or a pull request with the change. An issue is enough when the change is specific to your setup, or when you cannot share the code.

This repository is the original source of its skills. Its `LICENSE`, `LICENSES/` and the licence headers in its files record that, and anything derived from it should name it, as Derivative Works below sets out.

How you give back depends on how you took the skills.

### You copied the skills into another repository or an internal skills library

A copy does not track this repository: it stays at the version you copied until you copy again.

1. Keep `LICENSE` and `LICENSES/` with every copy, including a single skill folder, and keep the copyright and licence headers in the files. Add your own attribution beside them rather than replacing them.
2. Record where the copy came from: this repository, and the tag or commit you took (for example `pattern--v0.10.1`). Release tags are named after the skill, `<skill>--v<version>`.
3. To update, copy a newer release over it, then re-apply any local changes you still need. Keep local changes small and separate, so they are easy to carry forward.
4. To give a change back, raise an issue here, or apply the change to a fork of this repository and open a pull request. A change made only in the copy is lost at the next update.

### You cloned or forked the repository and keep it in step

1. Keep this repository as a remote so you can take its releases: `git remote add upstream https://github.com/dermot-obrien/ai-assisted-research.git`, then `git fetch upstream` and merge or rebase onto its `main` or a release tag.
2. Make your changes on a branch in your fork, and open a pull request against this repository's `main` for anything useful to others. Keep organisation-specific configuration out of the skills: it belongs in your workspace's bindings, which this repository never needs to see.
3. If you publish your fork, it is a derivative work: follow Derivative Works below.

## Contribution Process

### For Minor Changes

1. Fork the repository.
2. Make your changes.
3. Submit a pull request.

### For Significant Changes

1. **Open an Issue** describing what you want to contribute.
2. **Discuss** with maintainers.
3. **Fork and develop**.
4. **Submit PR** referencing the issue.

## Pull Request Guidelines

### PR Title Format

```
[TYPE] Brief description

Types:
- [AGENT] Agent protocol improvements
- [PRINCIPLE] Research principle changes
- [TEMPLATE] Template changes
- [DOCS] Documentation
- [FIX] Bug fixes
- [FEATURE] New features
```

### PR Description

```markdown
## Summary
What this PR does

## Type
- [ ] Agent improvement
- [ ] Research principle change
- [ ] Template change
- [ ] Documentation
- [ ] Bug fix
- [ ] New feature

## Testing
How you tested the changes (e.g., ran a research strand)

## Checklist
- [ ] Aligns with RMS Principles (PRINCIPLES.md)
- [ ] Domain-agnostic instructions
- [ ] Follows existing patterns
- [ ] Documentation updated
```

## Content Guidelines

### Domain-Agnostic

All agent and protocol contributions must be:

- **Generic**: No domain-specific assumptions (unless in a template example).
- **Reusable**: Works for various research fields (ML, Economics, Bio, etc.).
- **Metric-Driven**: Maintains the focus on quantifiable outcomes.

### Attribution

#### Acknowledging the Original

The Research Management System was created by **Dermot O'Brien**. When you:

- **Write** about the system (blog posts, articles).
- **Present** the framework (talks, academic conferences).
- **Teach** the framework (workshops, university courses).
- **Fork** or create derivatives.

Please consider crediting the original project and linking to this repository. This helps researchers find the source and supports the community.

#### Derivative Works

If you create a derivative or fork:

1. Keep the original LICENSE file.
2. Mention "Based on Research Management System by Dermot O'Brien" in your README.
3. Link to the original repository.

---

## Code of Conduct

### Standards

- Be respectful and inclusive.
- Support fellow researchers and developers.
- Accept constructive feedback on research protocols.
- Focus on the integrity of discovery.

## Questions?

- Open a [Discussion](https://github.com/dermot-obrien/ai-assisted-research/discussions)
- Create an [Issue](https://github.com/dermot-obrien/ai-assisted-research/issues)

---

Thank you for helping improve AI-Assisted Research!

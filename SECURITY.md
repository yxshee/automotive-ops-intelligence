# Security notes

## Known unpatched transitive advisory: `chromadb`

GitHub reports one critical advisory against `chromadb`, which reaches this
project only as a transitive dependency:

```
chromadb v1.1.1
└── crewai v1.15.6
    └── automotive-ops-intelligence
```

**There is no patched release.** The advisory covers `>= 1.0.0, <= 1.5.9` with
no fixed version published, so it cannot be resolved by upgrading. It also
cannot be removed: `crewai` depends on it directly for its memory and knowledge
features.

**Exposure in this project is nil in practice.** Nothing here imports
`chromadb`, instantiates a vector store, or enables CrewAI memory or knowledge
sources. No embedding is computed and no collection is created on any code
path, including live runs. The package is installed but never loaded.

This is recorded rather than dismissed. If `crewai` later makes the dependency
optional, or a patched `chromadb` ships, the lock should be updated.

## Reporting

Open an issue, or contact the maintainer directly for anything sensitive.

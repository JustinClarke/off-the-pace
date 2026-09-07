# Week 6 — CI/CD, Parity Cutover & the Exam 🏁🎓

**Theme:** package the whole thing as deployable code (DAB), run the full 60-model parity gate, then **sit and pass the exam.**
**Exam domain:** Implementing CI/CD (**10%**) + full-syllabus review.
**Deliverable:** pipeline + job deployed across dev/staging/prod via **Databricks Asset Bundles** · full
60-model parity gate green · ML retrained only if features shifted · **the exam, passed.** ✅

> ⚠️ **The rhythm bends this week — on purpose.** Mon–Wed you *ship*; Thu is *full revision*; Fri you *sit
> the exam*. Frontload the build so the back half is pure, calm exam prep. This is the home straight.

---

## The week (note the shift to exam mode)

| Day | Vibe | This week |
|---|---|---|
| [Mon](./monday.md) | Learn the *why* | Databricks Asset Bundles (DAB) |
| [Tue](./tuesday.md) | Build | Bundle the pipeline+job across targets + CI deploy |
| [Wed](./wednesday.md) | Build | The full 60-model parity cutover |
| [Thu](./thursday.md) | **Full-syllabus revision** | Practice exams + cheatsheet + drill weak spots |
| [Fri](./friday.md) | **🎓 Exam day** | Sit it. Pass it. Then the cutover decision. |

> 🧠 **ADHD note for exam week:** the danger now is *under*-prepping the boring logistics (proctor system
> check, ID, quiet room) and over-cramming. Thursday's checklist handles logistics so Friday-you just shows
> up. Trust the work — six weeks of building *is* the revision. Don't doom-spiral the night before.

---

## Momentum tracker

- [ ] Mon — bundle a single job with `bundle validate`
- [ ] Tue — dev/staging/prod targets + CI `bundle deploy` on push
- [ ] Wed — full-corpus build, **60/60 models parity-triaged** 🟢
- [ ] Thu — official practice exam ≥80%, `exam_cheatsheet.md` written from memory
- [ ] Fri — **EXAM PASSED** ✅🎉

---

## 🏁 Done means
- [ ] 60/60 models parity-triaged (clean, or diff documented as *intended*).
- [ ] Pipeline + job deployed via DAB across targets.
- [ ] ML retrained only if needed; app + ML code unchanged (that's the whole proof).
- [ ] **Exam passed.** ✅
- [ ] If Spark output proved better, open the cutover decision in [`SPARK_REBUILD_PLAN.md`](../../_wip/SPARK_REBUILD_PLAN.md).

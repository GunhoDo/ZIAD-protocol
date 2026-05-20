.PHONY: paper paper-tables p0 clean-paper

paper:
	bash scripts/build_paper.sh

paper-tables:
	bash scripts/render_paper_tables.sh

p0:
	bash scripts/run_p0.sh

clean-paper:
	rm -f paper/paper.pdf paper/*.aux paper/*.log paper/*.out paper/*.toc

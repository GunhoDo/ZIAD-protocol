.PHONY: paper p0 clean-paper

paper:
	bash scripts/build_paper.sh

p0:
	bash scripts/run_p0.sh

clean-paper:
	rm -f paper/paper.pdf paper/*.aux paper/*.log paper/*.out paper/*.toc

# Advanced llt Command Examples

This document showcases creative llt command patterns that leverage multiple uses of the same flags with different values to achieve powerful outcomes.

### Multi-Model Chain Processing

```bash
llt --model claude-3-sonnet --prompt "Explain quantum computing" \
    --complete \
    --xml_wrap explanation \
    --write explanations/quantum-draft.ll \
    --model deepseek-chat --load explanations/quantum-draft.ll \
    --complete \
    --xml_wrap technical \
    --write explanations/quantum-technical.ll \
    --model hermes-3-llama-3.1-405b-fp8 --load explanations/quantum-technical.ll \
    --complete \
    --xml_wrap simplified \
    --write explanations/quantum-final.ll
```

**Technical rationale**: This workflow leverages llt's ability to maintain conversation state across multiple model invocations. Each model progressively refines the output, with Claude generating the initial explanation, DeepSeek adding technical depth, and Hermes providing simplification. The XML wrapping creates clear semantic boundaries between each model's contribution, making the conversational pipeline traceable and enabling precise extraction of specific components later.

### Parallel Model Comparison

```bash
llt --prompt "Design a REST API for a social media platform" \
    --write api/base.ll \
    --model claude-3-5-sonnet-20241022 --load api/base.ll --complete --write api/claude.ll \
    --model deepseek-chat --load api/base.ll --complete --write api/deepseek.ll \
    --model hermes-3-llama-3.1-405b-fp8 --load api/base.ll --complete --write api/hermes.ll \
    --file api/claude.ll --xml_wrap claude --write api/comparison.ll \
    --file api/deepseek.ll --xml_wrap deepseek --write api/comparison.ll \
    --file api/hermes.ll --xml_wrap hermes --write api/comparison.ll
```

**Technical rationale**: This command exploits llt's file persistence mechanism to branch the conversation, generating parallel completions from different models with identical context. The multiple `--write` operations create separate snapshot files that preserve each model's unique response. The final phase uses XML wrapping to create a structured composite document with clearly demarcated sections, enabling systematic analysis of model performance differences.

### Multi-language Code Generator

```bash
llt --model claude-3-sonnet --prompt "Write a function that calculates Fibonacci sequence" \
    --complete --xml_wrap specification --write code/fibonacci-spec.ll \
    --load code/fibonacci-spec.ll --code_block python --execute --write code/fibonacci-python.ll \
    --load code/fibonacci-spec.ll --code_block javascript --execute --write code/fibonacci-js.ll \
    --load code/fibonacci-spec.ll --code_block rust --execute --write code/fibonacci-rust.ll
```

**Technical rationale**: This example demonstrates llt's capability to transform the same conceptual content across different programming paradigms. The `--code_block` flag transforms content into executable code blocks with proper syntax highlighting, while the `--execute` flag validates the correctness of generated code in each language. The conversation state is preserved and branched for each implementation, maintaining the original specification context while adapting the output format for each language.

### Progressive Document Assembly

```bash
llt --model deepseek-chat \
    --prompt "Write an introduction to neural networks" --complete --xml_wrap introduction --write nn/intro.ll \
    --prompt "Explain backpropagation in detail" --complete --xml_wrap backpropagation --write nn/backprop.ll \
    --prompt "Describe common activation functions" --complete --xml_wrap activation --write nn/activation.ll \
    --file nn/intro.ll --file nn/backprop.ll --file nn/activation.ll --xml_wrap tutorial \
    --write nn/complete-tutorial.ll
```

**Technical rationale**: This workflow exploits llt's file operations and XML manipulation to implement a content aggregation pipeline. Each section is generated independently to maintain focused context and quality, then assembled into a unified document. The XML wrapping creates semantic structure that preserves the hierarchical organization of content, enabling future operations like selective updating of specific sections without regenerating the entire document.

### Multi-stage Data Generation

```bash
llt --model hermes-3-llama-3.1-405b-fp8 \
    --prompt "Generate 5 customer profiles for an e-commerce site" \
    --complete --xml_wrap profiles --write data/profiles.ll \
    --load data/profiles.ll --prompt "For each customer profile, generate purchase history" \
    --complete --xml_wrap purchases --write data/purchases.ll \
    --load data/purchases.ll --prompt "Generate product recommendations based on profiles and purchases" \
    --complete --xml_wrap recommendations --write data/recommendations.ll \
    --load data/recommendations.ll --code_block json --write data/customer-data.ll
```

**Technical rationale**: This example showcases llt's ability to implement multi-stage data transformation pipelines. Each stage builds upon previous outputs, maintaining contextual coherence while adding new layers of information. The XML wrapping creates clear boundaries between data categories, while the final `--code_block json` operation transforms the narrative content into structured data format suitable for programmatic consumption.

### Multi-perspective Analysis

```bash
llt --file research-paper.txt \
    --model claude-3-5-sonnet-20241022 --prompt "Analyze from a scientific perspective" \
    --complete --xml_wrap scientific --write analysis/scientific.ll \
    --model o3-mini-high --file research-paper.txt --prompt "Analyze from a business perspective" \
    --complete --xml_wrap business --write analysis/business.ll \
    --model deepseek-chat --file research-paper.txt --prompt "Analyze from a societal impact perspective" \
    --complete --xml_wrap societal --write analysis/societal.ll \
    --file analysis/scientific.ll --file analysis/business.ll --file analysis/societal.ll \
    --xml_wrap comprehensive-analysis --write analysis/comprehensive.ll
```

**Technical rationale**: This workflow leverages llt's model-switching capability to obtain different analytical perspectives on the same source material. Each model is chosen for its strengths in specific domains, with independent processing threads that maintain focused context. The final aggregation phase creates a structured composite document where each perspective is clearly demarcated, enabling comprehensive cross-perspective analysis.

### Iterative Code Refinement

```bash
llt --file initial-code.py \
    --model deepseek-chat --prompt "Optimize this code for performance" \
    --complete --execute --xml_wrap performance --write code/perf-optimization.ll \
    --load code/perf-optimization.ll --prompt "Add comprehensive error handling" \
    --complete --execute --xml_wrap robust --write code/robust-code.ll \
    --load code/robust-code.ll --prompt "Add detailed documentation" \
    --complete --xml_wrap documented --write code/final-code.ll
```

**Technical rationale**: This example demonstrates llt's conversation state management for progressive code enhancement. Each stage builds upon the previous improvement while focusing on a specific aspect of code quality. The `--execute` operations validate that functional correctness is maintained throughout the transformation pipeline. XML wrapping creates traceable history of each enhancement stage, enabling rollback or comparison with earlier versions if needed.

### Multi-modal Context Assembly

```bash
llt --file dataset.csv --code_block csv \
    --write context/data.ll \
    --file visualization.png --prompt "Describe this visualization" \
    --complete --xml_wrap visual-analysis --write context/visual.ll \
    --file documentation.md --xml_wrap documentation \
    --write context/docs.ll \
    --file context/data.ll --file context/visual.ll --file context/docs.ll \
    --model claude-3-sonnet --prompt "Analyze all provided information and recommend next steps" \
    --complete --write context/recommendations.ll
```

**Technical rationale**: This workflow demonstrates llt's capability to process and integrate multi-modal inputs into a coherent analytical context. Different file types are processed with appropriate formatters (`--code_block csv` for structured data, image analysis for visual content, and markdown for documentation). The file persistence mechanism allows independent processing of each input type before aggregation, creating a comprehensive context that preserves the structure of diverse information sources.

### Cross-prompt Parameter Optimization

```bash
llt --model claude-3-sonnet --prompt "Write a sorting algorithm" \
    --temperature 0.7 --complete --xml_wrap creative --write algo/creative.ll \
    --model claude-3-sonnet --prompt "Write a sorting algorithm" \
    --temperature 0.2 --complete --xml_wrap precise --write algo/precise.ll \
    --model claude-3-sonnet --prompt "Write a sorting algorithm" \
    --temperature 0.0 --complete --xml_wrap deterministic --write algo/deterministic.ll \
    --file algo/creative.ll --file algo/precise.ll --file algo/deterministic.ll \
    --prompt "Compare these three sorting algorithms and analyze the effect of temperature" \
    --complete --write algo/temperature-analysis.ll
```

**Technical rationale**: This example exploits llt's parameter control to run controlled experiments on model behavior. By varying only the temperature parameter while keeping prompt and model constant, it isolates the impact of sampling temperature on algorithm design. The conversation state management creates independent branches for each parameter setting, while the final phase aggregates results for comparative analysis. This pattern is particularly valuable for systematic exploration of parameter spaces in model tuning.

### Chain-of-Tools Execution

```bash
llt --model claude-3-opus --prompt "Find all prime numbers between 1000 and 1100" \
    --complete --xml_wrap algorithm --write primes/algorithm.ll \
    --load primes/algorithm.ll --execute python --xml_wrap results --write primes/computed.ll \
    --load primes/computed.ll --prompt "Visualize these prime numbers and identify patterns" \
    --complete --xml_wrap analysis --write primes/analysis.ll \
    --load primes/analysis.ll --execute python --xml_wrap visualization --write primes/final.ll
```

**Technical rationale**: This workflow demonstrates llt's ability to interleave model-generated code with execution stages in a multi-step computational pipeline. The `--execute` flag runs generated Python code and captures the output, creating a feedback loop where execution results inform subsequent model prompts. This enables complex computational workflows where AI generates algorithms, the system executes them, and the AI interprets results—all while maintaining a persistent, traceable conversation state.

### Comparative Prompt Engineering

```bash
llt --prompt "What is artificial intelligence?" --xml_wrap question \
    --write prompts/base-question.ll \
    --load prompts/base-question.ll --prompt "Explain like I'm 5 years old" \
    --model claude-3-sonnet --complete --xml_wrap eli5 --write prompts/eli5.ll \
    --load prompts/base-question.ll --prompt "Explain like I'm a computer science PhD" \
    --model claude-3-sonnet --complete --xml_wrap phd --write prompts/phd.ll \
    --load prompts/base-question.ll --prompt "Explain like I'm a business executive" \
    --model claude-3-sonnet --complete --xml_wrap executive --write prompts/executive.ll \
    --file prompts/eli5.ll --file prompts/phd.ll --file prompts/executive.ll \
    --prompt "Analyze how these explanations differ and what makes each effective for its audience" \
    --complete --write prompts/audience-analysis.ll
```

**Technical rationale**: This example leverages llt's branching conversation capabilities to explore prompt engineering variations systematically. The base question is established once and persisted, then multiple prompting strategies are applied to the same foundation. Each variation is independently processed and stored, maintaining clean separation between approaches. The final aggregation phase enables meta-analysis of prompt engineering effectiveness, creating a structured learning environment for refining communication strategies.

### Document Translation Pipeline

```bash
llt --file technical-document.md --xml_wrap original \
    --write translation/source.ll \
    --load translation/source.ll --prompt "Translate to Spanish" \
    --model claude-3-5-sonnet-20241022 --complete --xml_wrap spanish --write translation/spanish.ll \
    --load translation/source.ll --prompt "Translate to French" \
    --model claude-3-5-sonnet-20241022 --complete --xml_wrap french --write translation/french.ll \
    --load translation/source.ll --prompt "Translate to German" \
    --model claude-3-5-sonnet-20241022 --complete --xml_wrap german --write translation/german.ll \
    --load translation/spanish.ll --prompt "Verify this Spanish translation for accuracy" \
    --model deepseek-chat --complete --xml_wrap verification --write translation/spanish-verified.ll
```

**Technical rationale**: This workflow demonstrates llt's suitability for content localization pipelines. The source document is preserved as an anchor point, with multiple translation branches maintaining independent conversation contexts. The XML wrapping clearly demarcates language boundaries, while the verification stage shows how translations can be independently validated. The file persistence mechanism creates an audit trail of the entire translation process, enabling traceability and quality control across multiple language versions.

### Interactive Learning Module Generation

```bash
llt --model claude-3-sonnet --prompt "Create a learning module about climate change" \
    --complete --xml_wrap outline --write education/outline.ll \
    --load education/outline.ll --prompt "Generate detailed content for each section" \
    --complete --xml_wrap content --write education/content.ll \
    --load education/content.ll --prompt "Create 5 quiz questions for each section" \
    --complete --xml_wrap questions --write education/questions.ll \
    --load education/content.ll --prompt "Create interactive exercises" \
    --complete --code_block javascript --execute --xml_wrap exercises \
    --write education/exercises.ll \
    --file education/content.ll --file education/questions.ll --file education/exercises.ll \
    --xml_wrap module --write education/complete-module.ll
```

**Technical rationale**: This example showcases llt's ability to implement complex content generation workflows with multiple interdependent components. The module outline establishes structure, followed by detailed content generation. The questions and exercises branches maintain contextual awareness of the content while focusing on specific pedagogical elements. The `--execute` flag validates interactive components, while the final aggregation creates a comprehensive learning module with clear organizational boundaries. This pattern is ideal for educational content development where consistency across components is essential.

### Experimental Data Analysis Pipeline

```bash
llt --file experiment-data.csv --code_block csv \
    --write analysis/data.ll \
    --load analysis/data.ll --prompt "Clean and preprocess this data" \
    --model claude-3-5-sonnet-20241022 --complete --code_block python \
    --execute --xml_wrap preprocessing --write analysis/preprocessed.ll \
    --load analysis/preprocessed.ll --prompt "Perform statistical analysis" \
    --complete --code_block python --execute --xml_wrap statistics \
    --write analysis/statistics.ll \
    --load analysis/preprocessed.ll --prompt "Generate visualizations" \
    --complete --code_block python --execute --xml_wrap visualizations \
    --write analysis/visualizations.ll \
    --file analysis/statistics.ll --file analysis/visualizations.ll \
    --prompt "Interpret these results and suggest conclusions" \
    --complete --xml_wrap interpretation --write analysis/complete.ll
```

**Technical rationale**: This workflow demonstrates llt's suitability for data science pipelines that combine code generation, execution, and interpretation. The conversation state preserves data context while enabling multiple analytical branches (statistics and visualizations) to operate independently. The `--execute` flags create runtime validation points, ensuring that generated code functions correctly with the actual data. The final interpretation phase synthesizes insights across statistical and visual analyses, creating a comprehensive analytical narrative with executable components.

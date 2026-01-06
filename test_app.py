from daggr import Workflow, GradioNode

if __name__ == "__main__":
    print("Creating workflow...")
    workflow = Workflow(name="Simple Text Processing Pipeline")

    print("Adding nodes...")
    text_generator = GradioNode(
        src="gradio/gpt2",
        name="Text Generator"
    )

    text_summarizer = GradioNode(
        src="gradio/distilbart-cnn-12-6",
        name="Text Summarizer"
    )

    workflow.add_node(text_generator)
    workflow.add_node(text_summarizer)

    print("Connecting nodes...")
    workflow.connect(
        source=text_generator,
        source_output="0",
        target=text_summarizer,
        target_input="text"
    )

    print("Marking interaction point...")
    workflow.mark_interaction(text_generator)

    print("Launching workflow UI...")
    workflow.launch()


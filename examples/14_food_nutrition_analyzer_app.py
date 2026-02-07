import random

import gradio as gr

from daggr import FnNode, GradioNode, Graph


def ensure_image_path(inputs, key="image"):
    img = inputs.get(key)
    if isinstance(img, dict) and "path" in img:
        inputs[key] = img["path"]
    return inputs


def create_nutrition_report(food_items: str, nutrition_analysis: str) -> str:
    import datetime

    report = f"""
# 🍽️ FOOD NUTRITION ANALYSIS REPORT
**Analyzed:** {datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p")}

---

## 🥗 IDENTIFIED FOODS & DESCRIPTION
{food_items}

---

## 📊 NUTRITIONAL ANALYSIS
{nutrition_analysis}

---

## 🏷️ DIETARY CLASSIFICATIONS

Based on the detected foods, this meal may be:
- ✅ **Vegetarian**: Check analysis above
- ✅ **Vegan**: Check analysis above  
- ✅ **Gluten-Free**: Check analysis above
- ✅ **Dairy-Free**: Check analysis above
- ✅ **Keto-Friendly**: Check analysis above
- ✅ **Low-Carb**: Check analysis above
- ✅ **High-Protein**: Check analysis above

---

## 📈 HEALTH INSIGHTS

### Nutritional Highlights:
- **Estimated Caloric Range**: See detailed analysis above
- **Macronutrient Balance**: Carbs/Protein/Fat ratio
- **Micronutrients**: Vitamins and minerals present
- **Fiber Content**: Digestive health benefits

### Dietary Recommendations:
- 💧 Remember to stay hydrated (8 glasses of water daily)
- 🥗 Balance your plate (50% vegetables, 25% protein, 25% carbs)
- ⏰ Consider portion sizes for your dietary goals
- 🏃 Pair with regular physical activity

---

## ⚠️ ALLERGEN WARNINGS

Common allergens to check for:
- [ ] Nuts and tree nuts
- [ ] Dairy products
- [ ] Gluten/wheat
- [ ] Shellfish/seafood
- [ ] Eggs
- [ ] Soy products

*Note: Always verify ingredients if you have food allergies*

---

## 🎯 MEAL TIMING SUGGESTIONS

**Best consumed:**
- 🌅 Breakfast: High-protein, complex carbs
- 🌞 Lunch: Balanced, moderate portions
- 🌙 Dinner: Lighter, easily digestible
- 🏋️ Post-Workout: Protein-rich recovery meal

---

## 📱 TRACK YOUR NUTRITION

Consider logging this meal in a nutrition tracking app:
- MyFitnessPal
- Cronometer  
- Lose It!
- Nutritionix

**Tip:** Take photos of your meals to maintain a visual food diary!
"""
    return report


def extract_calorie_summary(nutrition_analysis: str) -> str:
    summary = """🔢 **QUICK CALORIE & MACRO SUMMARY**

Based on the nutritional analysis:

**Total Estimated Calories:** Check detailed analysis
**Protein:** Estimate per serving
**Carbohydrates:** Estimate per serving  
**Fats:** Estimate per serving
**Fiber:** Estimate per serving

💡 *These are estimates. Actual values depend on portion sizes, cooking methods, and specific ingredients.*

📊 **Calorie Distribution:**
- Protein: ~30-35%
- Carbs: ~40-45%
- Fats: ~20-30%

🎯 **Portion Control Tips:**
- Use smaller plates
- Measure protein portions (palm-sized)
- Fill half your plate with vegetables
- Drink water before meals
"""
    return summary


generated_food = GradioNode(
    "hf-applications/Z-Image-Turbo",
    api_name="/generate_image",
    inputs={
        "prompt": gr.Textbox(
            label="🎨 Generate Food Image (Optional)",
            value="Professional food photography of a healthy salmon bowl with quinoa, avocado, cherry tomatoes, and mixed greens, overhead shot, natural lighting, 4k",
            lines=3,
        ),
        "height": 1024,
        "width": 1024,
        "seed": random.random,
    },
    outputs={
        "image": gr.Image(label="Generated Food Image"),
    },
)

uploaded_food = gr.Image(
    label="📸 OR Upload Your Food Photo",
    type="filepath",
    value=None,
)

food_detection = GradioNode(
    "gokaygokay/Florence-2",
    api_name="/process_image",
    preprocess=lambda x: ensure_image_path(x, "image"),
    inputs={
        "image": generated_food.image,
        "task_prompt": "Dense Region Caption",
        "text_input": None,
        "model_id": "microsoft/Florence-2-large",
    },
    outputs={
        "output_text": gr.Textbox(label="🍕 Detected Food Items & Description"),
        "output_image": gr.Image(label="🔍 Food Analysis View"),
    },
)

nutrition_analysis = GradioNode(
    "vikhyatk/moondream2",
    api_name="/answer_question",
    preprocess=lambda x: ensure_image_path(x, "img"),
    inputs={
        "img": generated_food.image,
        "prompt": """You are a certified nutritionist. Analyze this food image:

## FOOD IDENTIFICATION
List all visible food items and ingredients

## NUTRITIONAL BREAKDOWN
• Estimated calories (per serving and total)
• Protein (grams)
• Carbohydrates (grams)
• Fats (grams)
• Key vitamins and minerals

## DIETARY CLASSIFICATION
• Vegan/Vegetarian/Omnivore
• Gluten-free/Keto/Low-carb status
• Allergen warnings

## HEALTH ASSESSMENT
• Nutritional rating (1-10)
• Portion size evaluation
• Best meal timing
• Improvement suggestions

Provide specific quantities and actionable insights.""",
    },
    outputs={"response": gr.Textbox(label="🥗 Detailed Nutrition Analysis", lines=15)},
)

nutrition_report = FnNode(
    fn=create_nutrition_report,
    inputs={
        "food_items": food_detection.output_text,
        "nutrition_analysis": nutrition_analysis.response,
    },
    outputs={
        "report": gr.Markdown(label="📄 Complete Nutrition Report"),
    },
)

calorie_summary = FnNode(
    fn=extract_calorie_summary,
    inputs={
        "nutrition_analysis": nutrition_analysis.response,
    },
    outputs={
        "summary": gr.Textbox(label="⚡ Quick Calorie Info", lines=8),
    },
)

audio_summary = GradioNode(
    "innoai/Edge-TTS-Text-to-Speech",
    api_name="/tts_interface",
    inputs={
        "text": calorie_summary.summary,
        "voice": "en-US-JennyNeural - en-US (Female)",
        "rate": 0,
        "pitch": 0,
    },
    outputs={
        "generated_audio": gr.Audio(label="🔊 Audio Nutrition Summary"),
        "warning": gr.Markdown(visible=False),
    },
)

graph = Graph(
    name="🍽️ Food Nutrition & Calorie Analyzer",
    nodes=[
        generated_food,
        food_detection,
        nutrition_analysis,
        nutrition_report,
        calorie_summary,
        audio_summary,
    ],
)

if __name__ == "__main__":
    graph.launch()

import os
import threading
import time
import pytest
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright
from ase.build import molecule
from ase.calculators.emt import EMT
import numpy as np

# Adjust imports to local module structure
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from v_ase.viewer import find_free_port, view

def test_milestone_2_proof():
    print("Initializing H2O molecule with EMT calculator...")
    atoms = molecule("H2O")
    atoms.calc = EMT()
    port = find_free_port()
    
    original_positions = atoms.positions.copy()
    print(f"Original O atom position: {original_positions[0]}")
    
    # Store the result
    result = {"edited": None}
    
    def run_viewer():
        # block=True returns the edited atoms after Done/Cancel
        # We run it in a thread so Playwright can interact with it
        result["edited"] = view(atoms, block=True, port=port)
    
    viewer_thread = threading.Thread(target=run_viewer, daemon=True)
    viewer_thread.start()
    
    # Wait for server to start
    time.sleep(2)
    
    print("Starting Playwright automation...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except PlaywrightError as exc:
            pytest.skip(f"Playwright Chromium is not installed: {exc}")
        page = browser.new_page()
        
        # Load the viewer
        page.goto(f"http://127.0.0.1:{port}")
        
        # Wait for atoms to load.
        page.wait_for_selector("#prop-natoms:text-is('3')")
        page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 3")
        print("Atoms loaded in UI.")
        
        # 1. Click O (Select Oxygen). Use the actual projected mesh position
        # instead of assuming the atom sits at the window center.
        viewport = page.locator("#app-viewport")
        box = viewport.bounding_box()
        oxygen_screen = page.evaluate("""() => {
            const app = window.__ASE_APP__;
            const mesh = app.renderer.atomMeshByIndex.get(0);
            const p = mesh.position.clone().project(app.renderer.camera);
            const rect = app.renderer.domElement.getBoundingClientRect();
            return {
                x: rect.left + (p.x + 1) * rect.width / 2,
                y: rect.top + (-p.y + 1) * rect.height / 2
            };
        }""")
        page.mouse.click(oxygen_screen["x"], oxygen_screen["y"])
        
        # Check if selected count becomes 1
        # It might take a moment
        page.wait_for_selector("#prop-selected:has-text('1')")
        page.wait_for_function("window.__ASE_APP__.renderer.selectionOutlines.children.length >= 2")
        print("Oxygen atom selected.")
        
        # 2. Press G
        page.keyboard.press("g")
        print("Entered MOVE mode.")
        
        # 3. Press X
        page.keyboard.press("x")
        page.wait_for_function(
            "window.__ASE_APP__.transform.mode === 'MOVE' && "
            "window.__ASE_APP__.transform.axis === 'X' && "
            "window.__ASE_APP__.transform.axisGuides.X.visible"
        )
        print("Axis constrained to X.")
        
        # 4. Type 1.0
        page.keyboard.type("1.0")
        print("Entered 1.0 in command buffer.")

        # 5. Left click confirms the preview immediately, Blender-style.
        page.mouse.click(box["x"] + box["width"] / 2 + 80, box["y"] + box["height"] / 2)
        page.wait_for_function("window.__ASE_APP__.transform.mode === 'IDLE'")
        print("Committed movement to backend via left click.")
        
        # 6. Click Done
        page.click("#btn-done")
        print("Clicked DONE to finalize session.")
        
        browser.close()
        
    # Wait for viewer thread to return
    viewer_thread.join(timeout=5)
    edited = result["edited"]
    
    assert edited is not None, "view() did not return an Atoms object."
    
    new_positions = edited.positions
    print(f"New O atom position: {new_positions[0]}")
    
    # Check if X increased by 1.0
    expected_x = original_positions[0][0] + 1.0
    actual_x = new_positions[0][0]

    assert np.isclose(actual_x, expected_x, atol=1e-3), (
        f"Expected X={expected_x}, but got {actual_x}"
    )

if __name__ == "__main__":
    test_milestone_2_proof()

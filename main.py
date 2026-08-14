import flet as ft
from src.app import MineHosterApp

def main(page: ft.Page):
    app = MineHosterApp(page)
    app.initialize()

ft.app(target=main)

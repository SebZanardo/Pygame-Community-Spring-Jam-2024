import math
import pygame

from utilities.typehints import ActionBuffer, MouseBuffer
from config.input import InputState, MouseButton, Action
from baseclasses.scenemanager import Scene, SceneManager
from config.settings import WINDOW_CENTRE, WINDOW_WIDTH, WINDOW_HEIGHT
from components.hexagonalgrid import (
    SIZE,
    HEXAGONAL_NEIGHBOURS,
    OPEN_COLOUR,
    Biome,
    HexPosition,
    HexTile,
    HexagonalGrid,
    get_hex_corners,
    hex_to_world,
    world_to_hex,
    round_to_nearest_hex,
    render_hex,
    render_open_hex,
    render_highlighted_hex,
    render_preview_hex,
    generate_hex_art,
)
from components.tilemanager import TileManager, STARTING_BIOME
from components.camera import Camera
from components.ui import render_centered_text, PopupText
from utilities.spriteloading import slice_sheet
from components.animationplayer import AnimationPlayer


PREVIEW_OFFSET = SIZE * 2
PREVIEW_X = WINDOW_WIDTH - SIZE
PREVIEW_Y = SIZE / 2 + 2

HELD_X = SIZE
HELD_Y = WINDOW_CENTRE[1]

MOVE_X = WINDOW_CENTRE[0] - PREVIEW_OFFSET
MOVE_Y = WINDOW_CENTRE[1] - SIZE


class Game(Scene):
    def __init__(self, scene_manager: SceneManager) -> None:
        super().__init__(scene_manager)

        self.popup_font = pygame.freetype.Font("assets/joystix.otf", 8)
        self.popup_font.antialiased = False
        self.popup_font.fgcolor = (255, 255, 255)

        self.font = pygame.freetype.Font("assets/joystix.otf", 10)
        self.font.antialiased = False

        self.big_font = pygame.freetype.Font("assets/joystix.otf", 20)
        self.big_font.antialiased = False
        self.big_font.fgcolor = (255, 255, 255)

        self.BIOME_SPRITES = slice_sheet("assets/tiles-Sheet.png", 16, 16)
        self.BIOME_SPRITE_MAP = {
            Biome.SWAMP: [0, 0, 6],
            Biome.GRASS: [1, 1, 7],
            Biome.SAND: [2, 2, 8],
            Biome.FOREST: [3, 3, 9],
            Biome.MOUNTAIN: [4, 4, 10],
            Biome.SNOW: [5, 5, 11],
        }

        self.hex_grid = HexagonalGrid()
        start_hex = HexTile(
            HexPosition(0, 0, 0), [STARTING_BIOME] * 6, [None] * 6, None
        )
        start_hex.sector_sprites = generate_hex_art(
            start_hex.sides, self.BIOME_SPRITE_MAP
        )
        self.hex_grid.add_tile(start_hex)

        self.tile_manager = TileManager(5, 50)
        self.camera = Camera(0, 0, *WINDOW_CENTRE)

        self.hovered_tile = HexPosition(0, 0, 0)
        self.score = 0

        place_frames = []
        place_length = 16
        for i in range(place_length):
            frame = pygame.Surface((SIZE * 4, SIZE * 4), pygame.SRCALPHA)
            outer_corners = get_hex_corners(
                SIZE * 2, SIZE * 2, SIZE * (1 - i / (place_length * 4))
            )
            inner_corners = get_hex_corners(
                SIZE * 2, SIZE * 2, SIZE * (1.5 - i / (place_length * 2))
            )
            pygame.draw.polygon(
                frame, (255, 255, 255, i * (150 / place_length)), outer_corners, 2
            )
            pygame.draw.polygon(
                frame, (255, 255, 255, i * (150 / place_length)), inner_corners, 2
            )
            place_frames.append(frame)
        place_frames.reverse()
        self.place_animation = AnimationPlayer("place", place_frames, 0.05, False)
        self.place_location = (0, 0)

        self.edge_popup_text = [
            PopupText(1000, 1000, self.popup_font, "+10", 0.5) for _ in range(6)
        ]
        self.perfect_popup_text = [
            PopupText(1000, 1000, self.popup_font, "PERFECT", 0.5) for _ in range(2)
        ]

    def handle_input(
        self, action_buffer: ActionBuffer, mouse_buffer: MouseBuffer
    ) -> None:
        if action_buffer[Action.BACK][InputState.PRESSED]:
            self.scene_manager.switch_scene(None)
        if action_buffer[Action.RESTART][InputState.PRESSED]:
            self.scene_manager.switch_scene(Game)

        self.input_x, self.input_y = 0, 0
        mx, my = pygame.mouse.get_pos()
        dx = WINDOW_CENTRE[0] - mx
        dy = WINDOW_CENTRE[1] - my
        d = math.sqrt(dx**2 + dy**2)

        if abs(dx) > MOVE_X or abs(dy) > MOVE_Y:
            self.input_x = -dx / d
            self.input_y = -dy / d
        else:
            offset_mouse_position = self.camera.screen_to_world(mx, my)
            hex = world_to_hex(*offset_mouse_position)
            self.hovered_tile = round_to_nearest_hex(hex)

        self.hold = action_buffer[Action.HOLD][InputState.PRESSED]
        self.rotate = mouse_buffer[MouseButton.RIGHT][InputState.PRESSED]
        self.try_place = mouse_buffer[MouseButton.LEFT][InputState.PRESSED]

    def update(self, dt: float) -> None:
        self.camera.move(dt, self.input_x, self.input_y)

        if self.hold:
            self.tile_manager.swap_held_tile()

        if self.rotate:
            self.tile_manager.rotate_active_tile()

        if self.try_place and self.hex_grid.is_open(self.hovered_tile):
            tile = self.tile_manager.create_active_tile(self.hovered_tile)
            if tile is not None:
                tile.sector_sprites = generate_hex_art(
                    tile.sides, self.BIOME_SPRITE_MAP
                )

                self.hex_grid.add_tile(tile)

                # Scoring
                for i, neighbour in enumerate(HEXAGONAL_NEIGHBOURS):
                    position = self.hovered_tile + neighbour
                    adj_tile = self.hex_grid.get_tile(position)

                    if adj_tile is None:
                        continue

                    # If same biomes are touching
                    tile.sides_touching[i] = adj_tile.sides[(i + 3) % 6]
                    adj_tile.sides_touching[(i + 3) % 6] = tile.sides[i]
                    if tile.sides[i] == adj_tile.sides[(i + 3) % 6]:
                        popup_pos = hex_to_world(tile.position)
                        offset_pos = hex_to_world(neighbour)
                        edge_pos = (
                            popup_pos[0] + offset_pos[0] // 2,
                            popup_pos[1] + offset_pos[1] // 2,
                        )
                        self.edge_popup_text[i].move(*edge_pos)
                        self.score += 10
                        tile.matching_sides += 1
                        adj_tile.matching_sides += 1

                        if tile.matching_sides == 6:
                            self.score += 100
                            self.tile_manager.add_to_remaining(3)
                            self.perfect_popup_text[0].move(*popup_pos)
                        if adj_tile.matching_sides == 6:
                            self.score += 100
                            self.tile_manager.add_to_remaining(3)
                            self.perfect_popup_text[1].move(
                                *hex_to_world(adj_tile.position)
                            )

                self.tile_manager.get_next_tile()

                self.place_location = hex_to_world(tile.position)
                self.place_animation.reset()

        self.place_animation.update(dt)
        for text in self.edge_popup_text:
            text.update(dt)

        for text in self.perfect_popup_text:
            text.update(dt)

    def render(self, surface: pygame.Surface) -> None:
        surface.fill((83, 216, 251))

        for hex_position_tuple in self.hex_grid.get_open_tiles():
            render_open_hex(surface, self.camera, HexPosition(*hex_position_tuple))

        active_tile = self.tile_manager.create_active_tile(self.hovered_tile)
        if active_tile is not None:
            render_hex(surface, self.camera, active_tile, self.BIOME_SPRITES)

        for hex in self.hex_grid.get_placed_tiles():
            render_hex(surface, self.camera, hex, self.BIOME_SPRITES)

        matching_sides = [False] * 6
        if (
            self.hex_grid.is_open(self.hovered_tile)
            and self.tile_manager.get_active() is not None
        ):
            for i, neighbour in enumerate(HEXAGONAL_NEIGHBOURS):
                position = self.hovered_tile + neighbour
                adj_tile = self.hex_grid.get_tile(position)

                if adj_tile is None:
                    continue

                # If same biomes are touching
                if self.tile_manager.get_active()[i] == adj_tile.sides[(i + 3) % 6]:
                    matching_sides[i] = True

        render_highlighted_hex(surface, self.camera, self.hovered_tile, matching_sides)

        place_screen = self.camera.world_to_screen(*self.place_location)
        place_screen = (place_screen[0] - SIZE * 2, place_screen[1] - SIZE * 2)
        surface.blit(self.place_animation.get_frame(), place_screen)

        for text in self.edge_popup_text:
            text.render(surface, self.camera)

        for text in self.perfect_popup_text:
            text.render(surface, self.camera)

        pygame.draw.rect(
            surface,
            OPEN_COLOUR,
            ((0, 0), (WINDOW_WIDTH, WINDOW_CENTRE[1] - MOVE_Y)),
        )
        pygame.draw.rect(
            surface,
            OPEN_COLOUR,
            ((0, 0), (WINDOW_CENTRE[0] - MOVE_X, WINDOW_HEIGHT)),
        )
        pygame.draw.rect(
            surface,
            OPEN_COLOUR,
            (
                (WINDOW_CENTRE[0] + MOVE_X, 0),
                (WINDOW_CENTRE[0] - MOVE_X, WINDOW_HEIGHT),
            ),
        )
        pygame.draw.rect(
            surface,
            OPEN_COLOUR,
            ((0, WINDOW_CENTRE[1] + MOVE_Y), (WINDOW_WIDTH, WINDOW_CENTRE[1] - MOVE_Y)),
        )

        for i, preview in enumerate(self.tile_manager.get_preview()):
            if preview is None:
                break
            render_preview_hex(surface, PREVIEW_X, (i + 1) * PREVIEW_OFFSET, preview)

        held_tile = self.tile_manager.get_held()
        if held_tile is not None:
            render_preview_hex(surface, HELD_X, HELD_Y, held_tile)

        render_centered_text(surface, self.font, "HELD", (HELD_X, HELD_Y - SIZE - 16))

        render_centered_text(
            surface,
            self.big_font,
            f"{self.tile_manager.get_remaining()}",
            (PREVIEW_X, PREVIEW_Y),
        )

        render_centered_text(
            surface,
            self.font,
            f"{self.hovered_tile}",
            (WINDOW_CENTRE[0], WINDOW_HEIGHT - 10),
        )

        render_centered_text(
            surface, self.big_font, f"{self.score}", (WINDOW_CENTRE[0], PREVIEW_Y)
        )

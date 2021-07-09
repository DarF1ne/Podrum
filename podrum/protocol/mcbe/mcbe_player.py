#########################################################
#  ____           _                                     #
# |  _ \ ___   __| |_ __ _   _ _ __ ___                 #
# | |_) / _ \ / _` | '__| | | | '_ ` _ \                #
# |  __/ (_) | (_| | |  | |_| | | | | | |               #
# |_|   \___/ \__,_|_|   \__,_|_| |_| |_|               #
#                                                       #
# Copyright 2021 Podrum Team.                           #
#                                                       #
# This file is licensed under the GPL v2.0 license.     #
# The license file is located in the root directory     #
# of the source code. If not you may not use this file. #
#                                                       #
#########################################################

import math
import json
from podrum.event.default.player.player_chat_event import player_chat_event
from podrum.event.default.player.player_join_event import player_join_event
from podrum.event.default.player.player_move_event import player_move_event
from podrum.event.default.player.player_sneak_event import player_sneak_event
from podrum.event.default.player.player_sprint_event import player_sprint_event
from podrum.event.default.player.player_jump_event import player_jump_event
from podrum.event.default.player.player_form_response_event import player_form_response_event
from podrum.game_data.mcbe.item_states import item_states
from podrum.geometry.vector_2 import vector_2
from podrum.geometry.vector_3 import vector_3
from podrum.protocol.mcbe import packets
from podrum.protocol.mcbe.entity.metadata_storage import metadata_storage
from podrum.protocol.mcbe.mcbe_protocol_info import mcbe_protocol_info
from podrum.protocol.mcbe.packet.game_packet import game_packet
from podrum.protocol.mcbe.type.action_type import action_type
from podrum.protocol.mcbe.type.command_origin_type import command_origin_type
from podrum.protocol.mcbe.type.interact_type import interact_type
from podrum.protocol.mcbe.type.login_status_type import login_status_type
from podrum.protocol.mcbe.type.resource_pack_client_response_type import resource_pack_client_response_type
from podrum.protocol.mcbe.type.text_type import text_type
from podrum.protocol.mcbe.type.window_id_type import window_id_type
from podrum.protocol.mcbe.type.window_type import window_type
from podrum.task.immediate_task import immediate_task
from podrum.world.chunk.chunk import chunk
from queue import Queue
from rak_net.protocol.frame import frame
from threading import Thread
from time import sleep
import zlib

class mcbe_player:
    def __init__(self, connection: object, server: object, entity_id: int) -> None:
        self.connection: object = connection
        self.server: object = server
        self.entity_id: int = entity_id
        self.world: object = server.world
        self.metadata_storage: object = metadata_storage()
        self.attributes: list = []
        self.message_format: str = "<%username> %message"
        self.chunk_send_queue: object = Queue()
        self.start_chunk_send_workers(1)
            
    def chunk_send_worker(self) -> None:
        while True:
            if not self.chunk_send_queue.empty():
                item: tuple = self.chunk_send_queue.get()
                if item is None:
                    break
                if not self.world.has_loaded_chunk(item[0], item[1]):
                    self.send_network_chunk_publisher_update()
                    self.chunk_send_queue.put(item)
                else:
                    c: object = self.world.get_chunk(item[0], item[1])
                    self.send_chunk(c)
            else:
                sleep(0.05)
                    
    def start_chunk_send_workers(self, count: int) -> None:
        self.chunk_send_worker_count: int = count
        for i in range(0, count):
            Thread(target = self.chunk_send_worker).start()
        
    def send_start_game(self) -> None:
        if not self.world.has_player(self.identity):
            self.world.create_player(self.identity)
        self.position: object = self.world.get_player_position(self.identity)
        self.position.y += 1
        packet: object = packets.start_game_packet()
        packet.entity_id = self.entity_id
        packet.entity_runtime_id = self.entity_id
        packet.player_gamemode = 1
        packet.spawn = self.position
        packet.rotation = vector_2(0, 0)
        packet.seed = 0
        packet.spawn_biome_type = 0
        packet.custom_biome_name = "plains"
        packet.dimension = 0
        packet.generator = 2
        packet.world_gamemode = self.world.get_world_gamemode()
        packet.difficulty = 0
        packet.world_spawn = vector_3(0, 4.0, 0)
        packet.disable_achivements = False
        packet.time = 0
        packet.edu_offer = 0
        packet.edu_features = False
        packet.edu_product_id = ""
        packet.rain_level = 0
        packet.lightning_level = 0
        packet.confirmed_platform_locked = False
        packet.multiplayer_game = True
        packet.lan_broadcasting = True
        packet.xbox_live_broadcast_mode = 4
        packet.platform_broadcast_mode = 4
        packet.enable_commands = True
        packet.require_texture_pack = False
        packet.game_rules = {}
        packet.experiments = []
        packet.has_used_experiments = False
        packet.bonus_chest = False
        packet.start_map = False
        packet.permission_level = 1
        packet.chunk_tick_range = 0
        packet.locked_behavior_pack = False
        packet.locked_texture_pack = False
        packet.from_locked_template = False
        packet.only_msa_gamer_tags = False
        packet.from_world_template = False
        packet.world_template_option_locked = True
        packet.only_old_villagers = False
        packet.game_version = mcbe_protocol_info.mcbe_version
        packet.limited_world_width = 0
        packet.limited_world_height = 0
        packet.new_nether = False
        packet.experimental_gamplay = False
        packet.level_id = ""
        packet.world_name = self.world.get_world_name()
        packet.premium_world_template_id = ""
        packet.trial = False
        packet.movement_type = 0
        packet.movement_rewind_size = 0
        packet.server_authoritative_block_breaking = False
        packet.current_tick = 0
        packet.enchantment_seed = 0
        packet.item_states = item_states
        packet.multiplayer_correlation_id = ""
        packet.server_authoritative_inventories = False
        packet.server_engine = "Podrum"
        packet.encode()
        self.send_packet(packet.data)
        
    def send_item_component_packet(self) -> None:
        packet: object = packets.item_component_packet()
        packet.encode()
        self.send_packet(packet.data)
        
    def send_creative_content_packet(self) -> None:
        packet: object = packets.creative_content_packet()
        packet.entries = self.server.managers.item_manager.creative_items.values()
        packet.encode()
        self.send_packet(packet.data)
             
    def send_biome_definition_list_packet(self) -> None:
        packet: object = packets.biome_definition_list_packet()
        packet.encode()
        self.send_packet(packet.data)
        
    def send_available_entity_identifiers_packet(self) -> None:
        packet: object = packets.available_entity_identifiers_packet()
        packet.encode()
        self.send_packet(packet.data)

    def handle_login_packet(self, data: bytes) -> None:
        packet: object = packets.login_packet(data)
        packet.decode()
        for chain in packet.chain_data:
            if "identityPublicKey" in chain:
                self.identity_public_key: str = chain["identityPublicKey"]
            if "extraData" in chain:
                self.xuid: str = chain["extraData"]["XUID"]
                self.username: str = chain["extraData"]["displayName"]
                self.identity: str = chain["extraData"]["identity"]
        self.send_play_status(login_status_type.success)
        packet: object = packets.resource_packs_info_packet()
        packet.forced_to_accept = False
        packet.scripting_enabled = False
        packet.behavior_pack_infos = []
        packet.texture_pack_infos = []
        packet.encode()
        self.send_packet(packet.data)
        self.spawned: bool = False
        self.server.logger.info(f"{self.username} logged in with uuid {self.identity}.")

    def disconnect(self, message: str = "Disconnected from server.", *, hide_disconnect_screen: bool = False) -> None:
        packet: object = packets.disconnect_packet()
        packet.message = message
        packet.hide_disconnect_screen = hide_disconnect_screen
        packet.encode()
        self.send_packet(packet.data)
        
    def transfer(self, address: str, port: int = 19132) -> None:
        packet: object = packets.transfer_packet()
        packet.address = address
        packet.port = port
        packet.encode()
        self.send_packet(packet.data)

    def send_form(self, form_id: int, form: object) -> None:
        packet: object = packets.modal_form_request_packet()
        packet.form_id = form_id
        data = form.to_dict()
        packet.form_data = json.dumps(data)
        packet.encode()
        self.send_packet(packet.data) 

    def handle_modal_form_response_packet(self, data: bytes):
        packet: object = packets.modal_form_response_packet(data)
        packet.decode()
        data = json.loads(packet.form_data)
        form_event: object = player_form_response_event(packet.form_id, data, self)
        form_event.call()


    def handle_resource_pack_client_response_packet(self, data: bytes) -> None:
        packet: object = packets.resource_pack_client_response_packet(data)
        packet.decode()
        if packet.status == resource_pack_client_response_type.none:
            packet: object = packets.resource_pack_stack_packet()
            packet.forced_to_accept = False
            packet.behavior_pack_id_versions = []
            packet.texture_pack_id_versions = []
            packet.game_version = mcbe_protocol_info.mcbe_version
            packet.expirement_count = 0
            packet.experimental = False
            packet.encode()
            self.send_packet(packet.data)
        elif packet.status == resource_pack_client_response_type.has_all_packs:
            packet: object = packets.resource_pack_stack_packet()
            packet.forced_to_accept = False
            packet.behavior_pack_id_versions = []
            packet.texture_pack_id_versions = []
            packet.game_version = mcbe_protocol_info.mcbe_version
            packet.experiment_count = 0
            packet.experimental = False
            packet.encode()
            self.send_packet(packet.data)
        elif packet.status == resource_pack_client_response_type.completed:
            self.server.logger.success(f"{self.username} has all packs.")
            self.send_start_game()
            self.send_creative_content_packet()
            self.send_biome_definition_list_packet()
            self.send_metadata()
            self.send_attributes()
            self.send_available_commands()
            self.send_item_component_packet()
            self.send_available_entity_identifiers_packet()
            
    def handle_packet_violation_warning_packet(self, data: bytes) -> None:
        packet: object = packets.packet_violation_warning_packet(data)
        packet.decode()
        if packet.type == 0:
            error_message: str = ""
            temp: str = f", due to malformed packet ({hex(packet.violated_packet_id)})"
            if packet.severity == 0:
                error_message += f"Warning{temp}"
            elif packet.severity == 1:
                error_message += f"Final Warning{temp}"
            elif packet.severity == 2:
                error_message += f"Terminating connectinon{temp}"
            self.server.logger.error(error_message)
            if len(packet.message) > 0:
                self.server.logger.error(packet.message)
                
    def handle_request_chunk_radius_packet(self, data: bytes) -> None:
        packet: object = packets.request_chunk_radius_packet(data)
        packet.decode()
        self.view_distance: int = min(self.server.config.data["max_view_distance"], packet.chunk_radius)
        new_packet: object = packets.chunk_radius_updated_packet()
        new_packet.chunk_radius = self.view_distance
        new_packet.encode()
        self.send_packet(new_packet.data)
        Thread(target = self.send_chunks).start()
        if not self.spawned:
            self.send_play_status(login_status_type.spawn)
            self.spawned: bool = True  
            join_event: object = player_join_event(self)
            join_event.call()
            self.server.broadcast_message(player_join_event(self).join_message)
                
    def handle_move_player_packet(self, data: bytes):
        packet: object = packets.move_player_packet(data)
        packet.decode()
        #if math.floor(packet.position.x / (8 * 16)) != math.floor(self.position.x / (8 * 16)) or math.floor(packet.position.z / (8 * 16)) != math.floor(self.position.z / (8 * 16)):
            #Thread(target = self.send_chunks).start()
        old_position: object = self.position
        self.position: object = packet.position
        if math.floor(old_position.x) >> 4 != math.floor(self.position.x) >> 4 or math.floor(old_position.z) >> 4 != math.floor(self.position.z) >> 4:
            Thread(target = self.send_chunks).start()
        move_event: object = player_move_event(self, self.position)
        move_event.call()
        if move_event.canceled:
            self.position: object = old_position
            # Todo

    def handle_player_action_packet(self, data: bytes): # probably not cancelable
        packet: object = packets.player_action_packet(data)
        packet.decode()
        if packet.action in [action_type.start_sneak, action_type.stop_sneak]:
            sneak_event: object = player_sneak_event(self, False if packet.action == action_type.stop_sneak else True)
            sneak_event.call()
        elif packet.action in [action_type.start_sprint, action_type.stop_sprint]:
            sprint_event: object = player_sprint_event(self, False if packet.action == action_type.stop_sprint else True)
            sprint_event.call()
        elif packet.action == action_type.jump:
            jump_event: object = player_jump_event(self)
            jump_event.call()
        elif packet.action == action_type.start_sleeping:
            start_sleeping_event: object = player_start_sleeping_event(self)
            start_sleeping_event.call()

    def send_message(self, message: str, xuid: str = "", needs_translation: bool = False) -> None:
        new_packet: object = packets.text_packet()
        new_packet.type = text_type.raw
        new_packet.needs_translation = needs_translation
        new_packet.message = message
        new_packet.xuid = xuid
        new_packet.platform_chat_id = ""
        new_packet.encode()
        self.send_packet(new_packet.data)
        
    def broadcast_message(self, message: str, xuid: str = "", needs_translation: bool = False) -> None:
        self.server.send_message(message)
        for p in self.server.players.values():
            p.send_message(message, xuid, needs_translation)


    def send_chat_message(self, message: str) -> None:
        self.broadcast_message(self.message_format.replace("%username", self.username).replace("%message", message), self.xuid)
            
    def handle_text_packet(self, data: bytes) -> None:
        packet: object = packets.text_packet(data)
        packet.decode()
        if packet.type == text_type.chat:
            chat_event: object = player_chat_event(self, packet.message)
            chat_event.call()
            if not chat_event.canceled:
                 self.send_chat_message(packet.message)
                    
    def handle_interact_packet(self, data: bytes) -> None:
        packet: object = packets.interact_packet(data)
        packet.decode()
        if packet.action_id == interact_type.open_inventory:
            new_packet: object = packets.container_open_packet()
            new_packet.window_id = window_id_type.creative
            new_packet.window_type = window_type.inventory
            new_packet.coordinates = self.position
            new_packet.runtime_entity_id = self.entity_id
            new_packet.encode()
            #self.send_packet(new_packet.data)
            
            
    def handle_command_request_packet(self, data: bytes) -> None:
        packet: object = packets.command_request_packet(data)
        packet.decode()
        if packet.origin == command_origin_type.player:
            self.server.dispatch_command(packet.command[1:], self)

    def handle_packet(self, data: bytes) -> None:
        if data[0] == mcbe_protocol_info.login_packet:
            self.handle_login_packet(data)
        elif data[0] == mcbe_protocol_info.resource_pack_client_response_packet:
            self.handle_resource_pack_client_response_packet(data)
        elif data[0] == mcbe_protocol_info.packet_violation_warning_packet:
            self.handle_packet_violation_warning_packet(data)
        elif data[0] == mcbe_protocol_info.request_chunk_radius_packet:
            self.handle_request_chunk_radius_packet(data)
        elif data[0] == mcbe_protocol_info.move_player_packet:
            self.handle_move_player_packet(data)
        elif data[0] == mcbe_protocol_info.text_packet:
            self.handle_text_packet(data)
        elif data[0] == mcbe_protocol_info.player_action_packet:
            self.handle_player_action_packet(data)
        elif data[0] == mcbe_protocol_info.command_request_packet:
            self.handle_command_request_packet(data)
        elif data[0] == mcbe_protocol_info.modal_form_response_packet:
            self.handle_modal_form_response_packet(data)
        elif data[0] == mcbe_protocol_info.interact_packet:
            self.handle_interact_packet(data)

    def send_chunks(self) -> None:
        chunk_x_start: int = (math.floor(self.position.x) >> 4) - self.view_distance
        chunk_x_end: int = (math.floor(self.position.x) >> 4) + self.view_distance
        chunk_z_start: int = (math.floor(self.position.z) >> 4) - self.view_distance
        chunk_z_end: int = (math.floor(self.position.z) >> 4) + self.view_distance
        for chunk_x in range(chunk_x_start, chunk_x_end):
            for chunk_z in range(chunk_z_start, chunk_z_end):
                self.world.load_queue.put((chunk_x, chunk_z))
                self.chunk_send_queue.put((chunk_x, chunk_z))
        
    def send_available_commands(self) -> None:
        new_packet: object = packets.available_commands_packet()
        new_packet.values_len = 1
        new_packet.enum_values = []
        new_packet.suffixes = []
        new_packet.enums = []
        new_packet.command_data = []
        for command in self.server.managers.command_manager.commands:
            new_packet.command_data.append({
                "name": command.name,
                "description": command.description,
                "flags": 0,
                "permission_level": 0,
                "alias": 0,
                "overloads": []
            })
        new_packet.dynamic_enums = []
        new_packet.enum_constraints = []
        new_packet.encode()
        self.send_packet(new_packet.data)
            
    def send_network_chunk_publisher_update(self) -> None:
        new_packet: object = packets.network_chunk_publisher_update_packet()
        new_packet.x = math.floor(self.position.x)
        new_packet.y = math.floor(self.position.y)
        new_packet.z = math.floor(self.position.z)
        new_packet.chunk_radius = self.view_distance << 4
        new_packet.encode()
        self.send_packet(new_packet.data)
    
    def send_chunk(self, send_chunk: object) -> None:
        packet: object = packets.level_chunk_packet()
        packet.chunk_x = send_chunk.x
        packet.chunk_z = send_chunk.z
        packet.sub_chunk_count = send_chunk.get_sub_chunk_send_count()
        packet.use_caching = False
        packet.chunk_data = send_chunk.network_serialize()
        packet.encode()
        self.send_packet(packet.data)

    def send_play_status(self, status: int) -> None:
        packet: object = packets.play_status_packet()
        packet.status = status
        packet.encode()
        self.send_packet(packet.data)
        
    def send_metadata(self) -> None:
        packet: object = packets.set_entity_data_packet()
        packet.runtime_entity_id = self.entity_id
        packet.metadata = self.metadata_storage.metadata
        packet.tick = 0
        packet.encode()
        self.send_packet(packet.data)
            
    def send_attributes(self) -> None:
        packet: object = packets.update_attributes_packet()
        packet.runtime_entity_id = self.entity_id
        packet.attributes = self.attributes
        packet.tick = 0
        packet.encode()
        self.send_packet(packet.data)
    
    def send_packet(self, data: bytes) -> None:
        new_packet: object = game_packet()
        new_packet.write_packet_data(data)
        new_packet.encode()
        send_packet: object = frame()
        send_packet.reliability = 0
        send_packet.body = new_packet.data
        self.connection.add_to_queue(send_packet, False)

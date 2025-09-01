import chess
import chess.engine
import chess.pgn
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
from datetime import datetime
import json
import os

class ChessSandbox:
    def __init__(self, stockfish_path):
        self.engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
        self.board = chess.Board()
        self.move_history = []
        self.analysis_depth = 15
        self.saved_positions = []
        self.hint_showing = False
        self.flipped = False  # Pour savoir si l'échiquier est retourné
        
        # Interface
        self.root = tk.Tk()
        self.root.title("Chess Sandbox avec Stockfish")
        self.root.geometry("1200x800")
        
        self.setup_ui()
        self.update_display()

    def setup_ui(self):
        # Menu principal
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Nouvelle partie", command=self.new_game)
        file_menu.add_command(label="Charger FEN", command=self.load_fen)
        file_menu.add_command(label="Importer PGN", command=self.import_pgn)
        file_menu.add_command(label="Exporter PGN", command=self.export_pgn)
        file_menu.add_command(label="Sauvegarder position", command=self.save_position)
        file_menu.add_separator()
        file_menu.add_command(label="Quitter", command=self.close)
        menubar.add_cascade(label="Fichier", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Retourner l'échiquier", command=self.flip_board)
        menubar.add_cascade(label="Affichage", menu=view_menu)

        self.root.config(menu=menubar)

        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # === GAUCHE: Échiquier ===
        board_frame = ttk.LabelFrame(main_frame, text="Échiquier", padding="10")
        board_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Canvas pour l'échiquier
        self.canvas = tk.Canvas(board_frame, width=480, height=480, bg="white")
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_square_click)
        
        # Boutons de contrôle
        control_frame = ttk.Frame(board_frame)
        control_frame.pack(pady=10)
        
        ttk.Button(control_frame, text="⏮ Début", command=self.goto_start).grid(row=0, column=0, padx=2)
        ttk.Button(control_frame, text="◀ Retour", command=self.undo_move).grid(row=0, column=1, padx=2)
        ttk.Button(control_frame, text="▶ Refaire", command=self.redo_move).grid(row=0, column=2, padx=2)
        ttk.Button(control_frame, text="🔄 Nouvelle partie", command=self.new_game).grid(row=0, column=3, padx=2)
        ttk.Button(control_frame, text="↕️ Retourner", command=self.flip_board).grid(row=0, column=4, padx=2)
        
        # Boutons Stockfish
        stockfish_frame = ttk.Frame(board_frame)
        stockfish_frame.pack(pady=5)
        
        ttk.Button(stockfish_frame, text="🤖 Coup Stockfish", command=self.play_stockfish_move, 
                  style="Accent.TButton").grid(row=0, column=0, padx=2)
        ttk.Button(stockfish_frame, text="💡 Indice", command=self.show_hint).grid(row=0, column=1, padx=2)
        
        # Mode de jeu
        self.play_mode_var = tk.StringVar(value="manual")
        mode_frame = ttk.LabelFrame(board_frame, text="Mode de jeu", padding="5")
        mode_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(mode_frame, text="Manuel", variable=self.play_mode_var, 
                       value="manual").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="Jouer contre Stockfish (Blancs)", 
                       variable=self.play_mode_var, value="stockfish_black",
                       command=self.check_stockfish_turn).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="Jouer contre Stockfish (Noirs)", 
                       variable=self.play_mode_var, value="stockfish_white",
                       command=self.check_stockfish_turn).pack(side=tk.LEFT, padx=5)
        
        # === MILIEU: Analyse ===
        analysis_frame = ttk.LabelFrame(main_frame, text="Analyse Stockfish", padding="10")
        analysis_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Évaluation
        eval_frame = ttk.Frame(analysis_frame)
        eval_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(eval_frame, text="Évaluation:").grid(row=0, column=0, sticky=tk.W)
        self.eval_label = ttk.Label(eval_frame, text="0.00", font=("Arial", 16, "bold"))
        self.eval_label.grid(row=0, column=1, padx=10)
        
        # Barre d'évaluation
        self.eval_bar = ttk.Progressbar(eval_frame, length=200, mode='determinate')
        self.eval_bar.grid(row=0, column=2, padx=10)
        self.eval_bar['value'] = 50
        
        # Meilleurs coups
        ttk.Label(analysis_frame, text="Meilleurs coups:").pack(anchor=tk.W, pady=(10, 5))
        
        self.best_moves_text = scrolledtext.ScrolledText(analysis_frame, height=8, width=40)
        self.best_moves_text.pack(fill=tk.BOTH, expand=True)
        
        # Profondeur d'analyse
        depth_frame = ttk.Frame(analysis_frame)
        depth_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(depth_frame, text="Profondeur:").grid(row=0, column=0)
        self.depth_var = tk.IntVar(value=15)
        depth_spinbox = ttk.Spinbox(depth_frame, from_=5, to=30, textvariable=self.depth_var, width=10)
        depth_spinbox.grid(row=0, column=1, padx=10)
        ttk.Button(depth_frame, text="Analyser", command=self.analyze_position).grid(row=0, column=2)
        
        # === DROITE: Notation et historique ===
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Notation des coups
        notation_frame = ttk.LabelFrame(right_frame, text="Notation", padding="10")
        notation_frame.pack(fill=tk.BOTH, expand=True)
        
        self.notation_text = scrolledtext.ScrolledText(notation_frame, height=15, width=30)
        self.notation_text.pack(fill=tk.BOTH, expand=True)
        
        # Entrée de coup
        move_frame = ttk.Frame(right_frame)
        move_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(move_frame, text="Coup:").grid(row=0, column=0)
        self.move_entry = ttk.Entry(move_frame, width=10)
        self.move_entry.grid(row=0, column=1, padx=5)
        self.move_entry.bind("<Return>", lambda e: self.make_move_from_entry())
        ttk.Button(move_frame, text="Jouer", command=self.make_move_from_entry).grid(row=0, column=2)
        
        # Boutons d'import/export
        io_frame = ttk.Frame(right_frame)
        io_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(io_frame, text="📥 Importer PGN", command=self.import_pgn).pack(side=tk.LEFT, padx=2)
        ttk.Button(io_frame, text="📤 Exporter PGN", command=self.export_pgn).pack(side=tk.LEFT, padx=2)
        ttk.Button(io_frame, text="💾 Sauver position", command=self.save_position).pack(side=tk.LEFT, padx=2)
        
        # === BAS: Informations ===
        info_frame = ttk.Frame(main_frame)
        info_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        self.info_label = ttk.Label(info_frame, text="Trait aux Blancs")
        self.info_label.pack()
        
        # FEN
        fen_frame = ttk.Frame(info_frame)
        fen_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(fen_frame, text="FEN:").pack(side=tk.LEFT)
        self.fen_var = tk.StringVar()
        fen_entry = ttk.Entry(fen_frame, textvariable=self.fen_var, width=80)
        fen_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(fen_frame, text="Charger", command=self.load_fen).pack(side=tk.LEFT)
        
    def draw_board(self):
        """Dessine l'échiquier et les pièces"""
        self.canvas.delete("all")
        square_size = 60
        
        # Dessine les cases
        for row in range(8):
            for col in range(8):
                x1 = col * square_size
                y1 = row * square_size
                x2 = x1 + square_size
                y2 = y1 + square_size
                
                color = "#F0D9B5" if (row + col) % 2 == 0 else "#B58863"
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")
                
                # Coordonnées (adaptées selon l'orientation)
                if col == 0:
                    rank = str(8-row) if not self.flipped else str(row+1)
                    self.canvas.create_text(x1 + 5, y1 + 10, text=rank, 
                                          fill="black", font=("Arial", 10))
                if row == 7:
                    file = chr(97+col) if not self.flipped else chr(104-col)
                    self.canvas.create_text(x2 - 10, y2 - 5, text=file, 
                                          fill="black", font=("Arial", 10))
        
        # Dessine les pièces
        piece_symbols = {
            chess.PAWN: "♟♙", chess.KNIGHT: "♞♘", chess.BISHOP: "♝♗",
            chess.ROOK: "♜♖", chess.QUEEN: "♛♕", chess.KING: "♚♔"
        }
        
        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            if piece:
                # Calcul de la position selon l'orientation
                if not self.flipped:
                    row = 7 - (square // 8)
                    col = square % 8
                else:
                    row = square // 8
                    col = 7 - (square % 8)
                
                x = col * square_size + square_size // 2
                y = row * square_size + square_size // 2
                
                # Correction: index 1 pour blancs, 0 pour noirs
                symbol = piece_symbols[piece.piece_type][1 if piece.color else 0]
                self.canvas.create_text(x, y, text=symbol, font=("Arial", 40),
                                       fill="white" if piece.color else "black")
        
        # Surligne le dernier coup
        if self.board.move_stack:
            last_move = self.board.peek()
            for square in [last_move.from_square, last_move.to_square]:
                if not self.flipped:
                    row = 7 - (square // 8)
                    col = square % 8
                else:
                    row = square // 8
                    col = 7 - (square % 8)
                    
                x1 = col * square_size
                y1 = row * square_size
                x2 = x1 + square_size
                y2 = y1 + square_size
                self.canvas.create_rectangle(x1, y1, x2, y2, outline="yellow", width=3)
    
    def on_square_click(self, event):
        """Gère les clics sur l'échiquier"""
        square_size = 60
        col = event.x // square_size
        row = event.y // square_size
        
        # Calcul de la case selon l'orientation
        if not self.flipped:
            square = chess.square(col, 7 - row)
        else:
            square = chess.square(7 - col, row)
        
        square_name = chess.square_name(square)
        
        # Si on a déjà sélectionné une case
        if hasattr(self, 'selected_square'):
            # Essaye de jouer le coup
            try:
                move = self.board.find_move(self.selected_square, square)
                if move in self.board.legal_moves:
                    self.make_move(move)
            except:
                pass
            
            delattr(self, 'selected_square')
            self.draw_board()
        else:
            # Sélectionne une pièce
            piece = self.board.piece_at(square)
            if piece and piece.color == self.board.turn:
                self.selected_square = square
                # Surligne la case sélectionnée
                if not self.flipped:
                    col = square % 8
                    row = 7 - (square // 8)
                else:
                    col = 7 - (square % 8)
                    row = square // 8
                    
                x1 = col * square_size
                y1 = row * square_size
                x2 = x1 + square_size
                y2 = y1 + square_size
                self.canvas.create_rectangle(x1, y1, x2, y2, outline="green", width=3)
                
                # Montre les coups possibles
                for move in self.board.legal_moves:
                    if move.from_square == square:
                        to_square = move.to_square
                        if not self.flipped:
                            col = to_square % 8
                            row = 7 - (to_square // 8)
                        else:
                            col = 7 - (to_square % 8)
                            row = to_square // 8
                            
                        x = col * square_size + square_size // 2
                        y = row * square_size + square_size // 2
                        self.canvas.create_oval(x-10, y-10, x+10, y+10, 
                                               fill="green", outline="darkgreen")
    
    def make_move(self, move):
        """Joue un coup"""
        self.board.push(move)
        self.move_history = self.board.move_stack.copy()
        self.update_display()
        
        # Analyse automatique en arrière-plan
        threading.Thread(target=self.analyze_position, daemon=True).start()
        
        # Si on joue contre Stockfish, fait jouer l'ordinateur
        self.check_stockfish_turn()
    
    def check_stockfish_turn(self):
        """Vérifie si c'est au tour de Stockfish de jouer"""
        mode = self.play_mode_var.get()
        if mode == "stockfish_black" and not self.board.turn:  # Tour des noirs
            self.root.after(500, self.play_stockfish_move)
        elif mode == "stockfish_white" and self.board.turn:  # Tour des blancs
            self.root.after(500, self.play_stockfish_move)
    
    def play_stockfish_move(self):
        """Fait jouer Stockfish"""
        if self.board.is_game_over():
            return
        
        try:
            # Désactive temporairement les boutons
            self.info_label.config(text="Stockfish réfléchit...")
            self.root.update()
            
            # Demande le meilleur coup à Stockfish
            result = self.engine.play(self.board, chess.engine.Limit(time=1.0))
            
            # Joue le coup
            self.board.push(result.move)
            self.move_history = self.board.move_stack.copy()
            self.update_display()
            
            # Analyse la nouvelle position
            threading.Thread(target=self.analyze_position, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur Stockfish: {e}")
    
    def show_hint(self):
        """Affiche un indice (surligne le meilleur coup)"""
        if self.board.is_game_over():
            return
        
        try:
            # Trouve le meilleur coup
            result = self.engine.play(self.board, chess.engine.Limit(time=0.5))
            best_move = result.move
            
            # Redessine le plateau
            self.draw_board()
            
            # Surligne le meilleur coup en bleu
            square_size = 60
            
            # Case de départ
            from_square = best_move.from_square
            if not self.flipped:
                col = from_square % 8
                row = 7 - (from_square // 8)
            else:
                col = 7 - (from_square % 8)
                row = from_square // 8
                
            x1 = col * square_size
            y1 = row * square_size
            x2 = x1 + square_size
            y2 = y1 + square_size
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="blue", width=4)
            
            # Case d'arrivée
            to_square = best_move.to_square
            if not self.flipped:
                col = to_square % 8
                row = 7 - (to_square // 8)
            else:
                col = 7 - (to_square % 8)
                row = to_square // 8
                
            x1 = col * square_size
            y1 = row * square_size
            x2 = x1 + square_size
            y2 = y1 + square_size
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="lightblue", width=4)
            
            # Flèche
            if not self.flipped:
                from_x = (best_move.from_square % 8) * square_size + square_size // 2
                from_y = (7 - best_move.from_square // 8) * square_size + square_size // 2
                to_x = (best_move.to_square % 8) * square_size + square_size // 2
                to_y = (7 - best_move.to_square // 8) * square_size + square_size // 2
            else:
                from_x = (7 - best_move.from_square % 8) * square_size + square_size // 2
                from_y = (best_move.from_square // 8) * square_size + square_size // 2
                to_x = (7 - best_move.to_square % 8) * square_size + square_size // 2
                to_y = (best_move.to_square // 8) * square_size + square_size // 2
            
            self.canvas.create_line(from_x, from_y, to_x, to_y, 
                                   fill="blue", width=3, arrow=tk.LAST,
                                   arrowshape=(16, 20, 6))
            
            # Affiche aussi dans la zone d'analyse
            self.best_moves_text.insert(1.0, f"💡 Indice: {self.board.san(best_move)}\n\n")
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'obtenir un indice: {e}")
    
    def flip_board(self):
        """Retourne l'échiquier à 180 degrés"""
        self.flipped = not self.flipped
        self.draw_board()
    
    def make_move_from_entry(self):
        """Joue un coup depuis l'entrée texte"""
        try:
            move_text = self.move_entry.get().strip()
            move = self.board.parse_san(move_text)
            if move in self.board.legal_moves:
                self.make_move(move)
                self.move_entry.delete(0, tk.END)
            else:
                messagebox.showerror("Erreur", "Coup illégal")
        except:
            messagebox.showerror("Erreur", "Format de coup invalide")
    
    def undo_move(self):
        """Annule le dernier coup"""
        if self.board.move_stack:
            self.board.pop()
            self.update_display()
            threading.Thread(target=self.analyze_position, daemon=True).start()
    
    def redo_move(self):
        """Refait un coup annulé"""
        if len(self.move_history) > len(self.board.move_stack):
            move = self.move_history[len(self.board.move_stack)]
            self.board.push(move)
            self.update_display()
            threading.Thread(target=self.analyze_position, daemon=True).start()
    
    def goto_start(self):
        """Retourne au début de la partie"""
        while self.board.move_stack:
            self.board.pop()
        self.update_display()
        threading.Thread(target=self.analyze_position, daemon=True).start()
    
    def new_game(self):
        """Nouvelle partie"""
        self.board = chess.Board()
        self.move_history = []
        self.update_display()
        threading.Thread(target=self.analyze_position, daemon=True).start()
    
    def analyze_position(self):
        """Analyse la position avec Stockfish"""
        try:
            depth = self.depth_var.get()
            
            # Analyse avec plusieurs variantes
            info = self.engine.analyse(self.board, chess.engine.Limit(depth=depth), multipv=5)
            
            # Évaluation principale
            if isinstance(info, list):
                main_info = info[0]
            else:
                main_info = info
                info = [info]
            
            score = main_info["score"].relative
            
            # Met à jour l'évaluation
            if score.is_mate():
                eval_text = f"Mat en {score.mate()}"
                eval_value = 100 if score.mate() > 0 else 0
            else:
                cp = score.score()
                eval_text = f"{cp/100:.2f}"
                # Convertit en pourcentage pour la barre (limite à ±10)
                eval_value = 50 + min(max(cp/100, -10), 10) * 5
            
            # Met à jour l'interface dans le thread principal
            self.root.after(0, self._update_analysis_display, eval_text, eval_value, info)
            
        except Exception as e:
            print(f"Erreur d'analyse: {e}")
    
    def _update_analysis_display(self, eval_text, eval_value, info):
        """Met à jour l'affichage de l'analyse (thread principal)"""
        self.eval_label.config(text=eval_text)
        self.eval_bar['value'] = eval_value
        
        # Affiche les meilleures variantes
        self.best_moves_text.delete(1.0, tk.END)
        for i, variant in enumerate(info[:5]):
            if "pv" in variant and variant["pv"]:
                moves = variant["pv"][:5]  # Premiers coups de la variante
                score = variant["score"].relative
                
                if score.is_mate():
                    score_text = f"Mat en {score.mate()}"
                else:
                    score_text = f"{score.score()/100:.2f}"
                
                # Convertit les coups en notation
                temp_board = self.board.copy()
                move_text = []
                for move in moves:
                    if temp_board.turn == chess.WHITE:
                        move_text.append(f"{temp_board.fullmove_number}.")
                    move_text.append(temp_board.san(move))
                    temp_board.push(move)
                
                line = f"{i+1}. [{score_text}] {' '.join(move_text)}\n"
                self.best_moves_text.insert(tk.END, line)
    
    def update_display(self):
        """Met à jour l'affichage complet"""
        self.draw_board()
        
        # Met à jour la notation
        self.notation_text.delete(1.0, tk.END)
        game = chess.pgn.Game()
        game.setup(chess.Board())
        node = game
        
        for move in self.board.move_stack:
            node = node.add_variation(move)
        
        self.notation_text.insert(1.0, str(game.mainline_moves()).replace("(", "").replace(")", ""))
        
        # Met à jour les infos
        if self.board.is_checkmate():
            result = "Échec et mat! " + ("Les Noirs" if self.board.turn else "Les Blancs") + " gagnent!"
        elif self.board.is_stalemate():
            result = "Pat!"
        elif self.board.is_insufficient_material():
            result = "Matériel insuffisant!"
        elif self.board.is_fifty_moves():
            result = "Règle des 50 coups!"
        else:
            result = "Trait aux " + ("Blancs" if self.board.turn else "Noirs")
            if self.board.is_check():
                result += " (Échec!)"
        
        self.info_label.config(text=result)
        
        # Met à jour FEN
        self.fen_var.set(self.board.fen())
    
    def load_fen(self):
        """Charge une position FEN"""
        try:
            fen = self.fen_var.get()
            self.board = chess.Board(fen)
            self.move_history = []
            self.update_display()
            threading.Thread(target=self.analyze_position, daemon=True).start()
        except:
            messagebox.showerror("Erreur", "FEN invalide")
    
    def import_pgn(self):
        """Importe une partie PGN"""
        filename = filedialog.askopenfilename(
            title="Importer PGN",
            filetypes=[("Fichiers PGN", "*.pgn"), ("Tous les fichiers", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    game = chess.pgn.read_game(f)
                
                self.board = game.board()
                for move in game.mainline_moves():
                    self.board.push(move)
                
                self.move_history = self.board.move_stack.copy()
                self.goto_start()  # Retourne au début pour pouvoir rejouer
                
                messagebox.showinfo("Succès", "Partie importée!")
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible d'importer: {e}")
    
    def export_pgn(self):
        """Exporte la partie en PGN"""
        filename = filedialog.asksaveasfilename(
            title="Exporter PGN",
            defaultextension=".pgn",
            filetypes=[("Fichiers PGN", "*.pgn"), ("Tous les fichiers", "*.*")]
        )
        
        if filename:
            try:
                game = chess.pgn.Game()
                game.headers["Event"] = "Chess Sandbox"
                game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
                game.headers["White"] = "Joueur 1"
                game.headers["Black"] = "Joueur 2"
                
                node = game
                temp_board = chess.Board()
                for move in self.board.move_stack:
                    node = node.add_variation(move)
                    temp_board.push(move)
                
                with open(filename, 'w') as f:
                    f.write(str(game))
                
                messagebox.showinfo("Succès", "Partie exportée!")
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible d'exporter: {e}")
    
    def save_position(self):
        """Sauvegarde la position actuelle"""
        name = tk.simpledialog.askstring("Sauvegarder", "Nom de la position:")
        if name:
            position = {
                "name": name,
                "fen": self.board.fen(),
                "moves": [move.uci() for move in self.board.move_stack],
                "date": datetime.now().isoformat()
            }
            self.saved_positions.append(position)
            
            # Sauvegarde dans un fichier
            try:
                with open("chess_positions.json", "w") as f:
                    json.dump(self.saved_positions, f, indent=2)
                messagebox.showinfo("Succès", "Position sauvegardée!")
            except:
                messagebox.showerror("Erreur", "Impossible de sauvegarder")
    
    def run(self):
        """Lance l'application"""
        # Charge les positions sauvegardées
        try:
            with open("chess_positions.json", "r") as f:
                self.saved_positions = json.load(f)
        except:
            self.saved_positions = []
        
        # Analyse initiale
        threading.Thread(target=self.analyze_position, daemon=True).start()
        
        # Lance l'interface
        self.root.mainloop()
    
    def close(self):
        """Ferme l'application"""
        self.engine.quit()
        self.root.destroy()

if __name__ == "__main__":
    stockfish_path = r"C:\Users\marvi\Downloads\stockfish-windows-x86-64-avx2\stockfish\stockfish-windows-x86-64-avx2.exe"
    
    app = ChessSandbox(stockfish_path)
    try:
        app.run()
    finally:
        app.engine.quit()

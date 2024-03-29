
from numpy.lib.function_base import place
import numpy as np
from  alm_actif.fonctionsfinance import valeur_marche_oblig, duration_obligatioin
import logging


class portefeuille_financier():
    """
        Classe representant le portefeuille financier pour la modelisation de l'actif, sa projection et ses interactions.
        Cette classe permet d'instancier et d'utiliser un objet representant l'actif avec ses différents type d'actifs et ses fonctions.
    """
    def __init__(self, portefeuille_action, portefeuille_oblig, portefeuille_immo, 
                        portefeuille_treso, scena_eco_action, scena_eco_oblig, scena_eco_immo, scena_eco_treso, alloc_strat_cible_portfi):
        """
            Constructeur de la classe *portefeuille_financier* de l'objet portefeuille financier.

            :param portefeuille_action: dataframe du portefeuille action
            :param portefeuille_oblig:  dataframe du portefeuille obligation
            :param portefeuille_immo:  dataframe du portefeuille immobilier
            :param portefeuille_treso:  dataframe du portefeuille tresorerie
            :param scena_eco_action:  dataframe du scenarios economiques des actions
            :param scena_eco_oblig: dataframe du scenarios economiques des obligations
            :param scena_eco_immo: dataframe des scenarios economiques pour l'immobilier
            :param scena_eco_treso: dataframe du scenarios economiques pour la tresorerie 
            :param alloc_strat_cible_portfi: dictionnaire de l'allocation stratégique cible du portefeuille financier.

            :returns: objet de la classer *portefeuille_financier*.
        """
        self.portefeuille_action = portefeuille_action
        self.portefeuille_oblig = portefeuille_oblig
        self.portefeuille_immo = portefeuille_immo
        self.portefeuille_treso = portefeuille_treso
        self.scena_eco_action = scena_eco_action
        self.scena_eco_oblig = scena_eco_oblig
        self.scena_eco_immo = scena_eco_immo
        self.scena_eco_treso = scena_eco_treso
        self.allocation_courante = {}
        self.alloc_strat_cible_portfi = alloc_strat_cible_portfi
        self.plus_moins_value_realised_total = 0
        self.plus_moins_value_realised_oblig = 0
        self.plus_moins_value_realised_action = 0
        self.plus_moins_value_realised_immo = 0
        self.reserve_capitalisation = 0
        self.provision_risque_exigibilite = 0
        self.resultat_financier = 0

    def veillissement_treso(self, t, maturite):
        """
            Vieillisement du portefeuille de trésorerie par projection 
            sur un an avec calcul du rendement
        """
        self.portefeuille_treso['t'] = t
        # self.portefeuille_treso['rdt'] = (1 + self.scena_eco_treso.iloc[1,t]) / (1 + self.scena_eco_treso.iloc[1,t-1]) - 1
        self.portefeuille_treso['rdt'] = 0.001
        self.portefeuille_treso['val_marche_fin'] = self.portefeuille_treso['val_marche_fin'] + self.portefeuille_treso['val_marche'] * (1 + self.portefeuille_treso['rdt'] * maturite)
        self.portefeuille_treso['val_nc'] = self.portefeuille_treso['val_marche'] * (1 + self.portefeuille_treso['rdt'] * maturite) 

    def veillissement_immo(self, t):
        """
            Vieillisement du portefeuille immobilier par projection sur un an avec calcul des loyers versés et du rendement

            :param t: (Int) année t de projection

            :returns: None, vieilli d'une année le portefeuille immo de l'objet courant
        """
        self.portefeuille_immo['t'] = t
        self.portefeuille_immo['rdt'] = ((self.scena_eco_immo.iloc[1,t] / self.scena_eco_immo.iloc[1,t-1]) - 1) + (self.portefeuille_immo['tx_loyer'] * self.portefeuille_immo['ind_invest'])
        self.portefeuille_immo['loyer'] = self.portefeuille_immo['val_marche'] * np.sqrt(1 + self.portefeuille_immo['rdt']) * self.portefeuille_immo['tx_loyer']
        self.portefeuille_immo['val_marche_fin'] = self.portefeuille_immo['val_marche'] * (1 + self.portefeuille_immo['rdt'])
        self.portefeuille_immo['dur_det'] = self.portefeuille_immo['dur_det'] + 1
        self.portefeuille_immo['pvl'] = self.portefeuille_immo.apply(lambda row : row['val_marche']-row['val_nc'] if row['val_marche']>row['val_nc'] else 0, axis = 1)
        self.portefeuille_immo['mvl'] = self.portefeuille_immo.apply(lambda row : row['val_marche']-row['val_nc'] if row['val_marche']<=row['val_nc'] else 0, axis = 1)

    def veillissement_obligation(self, scenario, t):
        """
            Vieillisement du portefeuille obligation par projection sur un an avec calcul des coupons versés et du rendement
            :param t: (Int) année t de projection

            :returns: None, vieilli d'une année le portefeuille obligation de l'objet courant
        """
        courbe = self.scena_eco_oblig.loc[(self.scena_eco_oblig['scenario']==scenario) & (self.scena_eco_oblig['month']==t),['maturities','rates']]
        self.portefeuille_oblig['t'] = t
        self.portefeuille_oblig['coupon'] = self.portefeuille_oblig['tx_coupon'] * self.portefeuille_oblig['nominal'] * self.portefeuille_oblig['par'] * self.portefeuille_oblig['nb_unit']  
        self.portefeuille_oblig['val_marche_fin'] = self.portefeuille_oblig.apply(lambda row : valeur_marche_oblig(row['tx_coupon'], row['nominal'], courbe, row['mat_res'], t), axis = 1)
        self.portefeuille_oblig['duration'] = self.portefeuille_oblig.apply(lambda row : duration_obligatioin(row['tx_coupon'], row['nominal'], courbe, row['mat_res'], t), axis = 1)
        self.portefeuille_oblig['zspread'] = 0
        self.portefeuille_oblig['dur_det'] = self.portefeuille_oblig['dur_det'] + 1
        self.portefeuille_oblig['mat_res'] = self.portefeuille_oblig['mat_res'] + 1
        self.portefeuille_oblig['surcote_decote'] = (self.portefeuille_oblig['nominal'] - self.portefeuille_oblig['val_nc']) / self.portefeuille_oblig['mat_res']
        self.portefeuille_oblig['pvl'] = self.portefeuille_oblig.apply(lambda row : row['val_marche']-row['val_nc'] if row['val_marche']>row['val_nc'] else 0, axis = 1)
        self.portefeuille_oblig['mvl'] = self.portefeuille_oblig.apply(lambda row : row['val_marche']-row['val_nc'] if row['val_marche']<=row['val_nc'] else 0, axis = 1)
        
    def veillissement_action(self, t):
        """
            Vieillisement du portefeuille action par projection sur un an avec calcul des dividendes versées et des du rendement
            :param t: (Int) année t de projection

            :returns: None, vieilli d'une année le portefeuille action de l'objet courant
        """
        self.portefeuille_action['t'] = t
        self.portefeuille_action['rdt'] = ((self.scena_eco_action.iloc[1,t] / self.scena_eco_action.iloc[1,t-1]) - 1) + (self.portefeuille_action['div'] * self.portefeuille_action['ind_invest'])
        self.portefeuille_action['dividende'] = self.portefeuille_action['val_marche'] * np.sqrt(1 + self.portefeuille_action['rdt']) * self.portefeuille_action['div']
        self.portefeuille_action['val_marche_fin'] = self.portefeuille_action['val_marche'] * (1 + self.portefeuille_action['rdt'])
        self.portefeuille_action['dur_det'] = self.portefeuille_action['dur_det'] + 1
        self.portefeuille_action['pvl'] = self.portefeuille_action.apply(lambda row : row['val_marche']-row['val_nc'] if row['val_marche']>row['val_nc'] else 0, axis = 1)
        self.portefeuille_action['mvl'] = self.portefeuille_action.apply(lambda row : row['val_marche']-row['val_nc'] if row['val_marche']<=row['val_nc'] else 0, axis = 1)
        
    def calcul_assiette_tresorerie(self, flux):
        """
            Calcul de l'assiette de treso =
            (dividendes + coupons + remboursement de nominal + loyer immo + interets monetaires)
            - (frais de l'actif + frais du passif + prestations rachats + prestations deces + revalorisation de prestations)

            :param total_frais_passif: (Float) montant total des frais engendrés par l'activité du passif
            :param total_prestations_passif: (Float) montant total des prestations 

            :returns: None, ajout au portefeuille des différents flux de produits et charges du portefeuille financier 
        """
        self.portefeuille_treso["val_marche_fin"] = self.portefeuille_treso["val_marche"] \
                                                + np.sum(self.portefeuille_action["val_marche"] * self.portefeuille_action["div"]) \
                                                + np.sum(self.portefeuille_immo["val_marche"] * self.portefeuille_immo["tx_loyer"]) \
                                                + np.sum(self.portefeuille_oblig["nominal"] * self.portefeuille_oblig["tx_coupon"]) \
                                                + np.sum(self.portefeuille_oblig.loc[self.portefeuille_oblig['mat_res'] == 0,'nominal']) \
                                                + flux

    def debit_credit_tresorerie(self, montant):
        """
            :param montant: (Numeric) Montant à debiter ou à créditer à la tresorerie.

            :returns: (None), 
        """
        self.portefeuille_treso["val_marche"] = self.portefeuille_treso["val_marche"] + montant

    def calcul_alloc_strateg_crt(self):
        """
            Calcul allocation courante du portefeuille financier

            :param : None

            :returns: None, calcul l'allocation stratégieu courante du portefeuille
        """
        try:
            self.allocation_courante  = {'somme_vm_action': sum(self.portefeuille_action['val_marche_fin']),
                                        'somme_vm_oblig': sum(self.portefeuille_oblig['val_marche_fin']),
                                        'somme_vm_immo': sum(self.portefeuille_immo['val_marche_fin']),
                                        'somme_vm_treso': sum(self.portefeuille_treso['val_marche_fin']),
                                        'propor_action': sum(self.portefeuille_action['val_marche_fin']) / (sum(self.portefeuille_action['val_marche_fin'])+sum(self.portefeuille_oblig['val_marche_fin'])+sum(self.portefeuille_immo['val_marche_fin'])+sum(self.portefeuille_treso['val_marche_fin'])),
                                        'propor_oblig': sum(self.portefeuille_oblig['val_marche_fin']) / (sum(self.portefeuille_action['val_marche_fin'])+sum(self.portefeuille_oblig['val_marche_fin'])+sum(self.portefeuille_immo['val_marche_fin'])+sum(self.portefeuille_treso['val_marche_fin'])),
                                        'propor_immo': sum(self.portefeuille_immo['val_marche_fin']) / (sum(self.portefeuille_action['val_marche_fin'])+sum(self.portefeuille_oblig['val_marche_fin'])+sum(self.portefeuille_immo['val_marche_fin'])+sum(self.portefeuille_treso['val_marche_fin'])),
                                        'propor_treso': sum(self.portefeuille_treso['val_marche_fin']) / (sum(self.portefeuille_action['val_marche_fin'])+sum(self.portefeuille_oblig['val_marche_fin'])+sum(self.portefeuille_immo['val_marche_fin'])+sum(self.portefeuille_treso['val_marche_fin'])),
                                        'total_vm_portfi': sum(self.portefeuille_action['val_marche_fin']) + sum(self.portefeuille_oblig['val_marche_fin']) + sum(self.portefeuille_immo['val_marche_fin']) + sum(self.portefeuille_treso['val_marche_fin'])}
        except KeyError:
            self.allocation_courante  = {'somme_vm_action': sum(self.portefeuille_action['val_marche']),
                                        'somme_vm_oblig': sum(self.portefeuille_oblig['val_marche']),
                                        'somme_vm_immo': sum(self.portefeuille_immo['val_marche']),
                                        'somme_vm_treso': sum(self.portefeuille_treso['val_marche']),
                                        'propor_action': sum(self.portefeuille_action['val_marche']) / (sum(self.portefeuille_action['val_marche'])+sum(self.portefeuille_oblig['val_marche'])+sum(self.portefeuille_immo['val_marche'])+sum(self.portefeuille_treso['val_marche'])),
                                        'propor_oblig': sum(self.portefeuille_oblig['val_marche']) / (sum(self.portefeuille_action['val_marche'])+sum(self.portefeuille_oblig['val_marche'])+sum(self.portefeuille_immo['val_marche'])+sum(self.portefeuille_treso['val_marche'])),
                                        'propor_immo': sum(self.portefeuille_immo['val_marche']) / (sum(self.portefeuille_action['val_marche'])+sum(self.portefeuille_oblig['val_marche'])+sum(self.portefeuille_immo['val_marche'])+sum(self.portefeuille_treso['val_marche'])),
                                        'propor_treso': sum(self.portefeuille_treso['val_marche']) / (sum(self.portefeuille_action['val_marche'])+sum(self.portefeuille_oblig['val_marche'])+sum(self.portefeuille_immo['val_marche'])+sum(self.portefeuille_treso['val_marche'])),
                                        'total_vm_portfi': sum(self.portefeuille_action['val_marche']) + sum(self.portefeuille_oblig['val_marche']) + sum(self.portefeuille_immo['val_marche']) + sum(self.portefeuille_treso['val_marche'])}



    def allocation_strategique(self, t):
        """
        L'allocation stratégique vise à créer une clé de répartition sur différentes classes d’actifs : actions, obligations, liquidités, etc

        Cette fonction permet de faire l'allocation strategique du portefeuille suite à l'evolution des valeurs de marchés des actifs à l'an t en fonction
        de l'allocation strategique cible. Après évaluation des écarts par rapport à l'allocation cible des opérations d'achats-ventes sont effectuées afin
        de correspondre à l'allocation cible

        :param t: (Int) année t de projection

        :returns: None, Réalocation stratégique du portefeuille financier de l'objet en cours.
        """
        # Calcul de l'allocaiton strategique courante
        self.calcul_alloc_strateg_crt()
        # initialisation des plus ou moins value réalisées
        self.plus_moins_value_realised_oblig = 0
        self.plus_moins_value_realised_action = 0
        self.plus_moins_value_realised_immo = 0
        # Montant total de l'actif à allouer après versement des prestations
        # montant_total_actif_a_allouer = self.allocation_courante['total_vm_portfi'] - prestations_en_t
        # Calcul des opération à effecteuer pour atteindre l'allocation strategique cible après prestations et mise à jour des VM des actifs
        calcul_operation_alm_vm = {'action' : self.alloc_strat_cible_portfi["propor_action_cible"] * self.allocation_courante['total_vm_portfi'] - self.allocation_courante['somme_vm_action'],
                                    'oblig' : self.alloc_strat_cible_portfi["propor_oblig_cible"] * self.allocation_courante['total_vm_portfi'] - self.allocation_courante['somme_vm_oblig'],
                                    'immo' : self.alloc_strat_cible_portfi["propor_immo_cible"] * self.allocation_courante['total_vm_portfi'] - self.allocation_courante['somme_vm_immo'],
                                    'treso' : self.alloc_strat_cible_portfi["propor_treso_cible"] * self.allocation_courante['total_vm_portfi'] - self.allocation_courante['somme_vm_treso']}
        # Operations achats-ventes action
        if calcul_operation_alm_vm['action'] > 0:
            self.acheter_des_actions(calcul_operation_alm_vm['action'])
        elif calcul_operation_alm_vm['action'] < 0:
            self.vendre_des_actions(calcul_operation_alm_vm['action'])
        # Operations achats-ventes immo
        if calcul_operation_alm_vm['immo'] > 0:
            self.acheter_des_immo(calcul_operation_alm_vm['immo'])
        elif calcul_operation_alm_vm['immo'] < 0:
            self.vendre_des_immo(calcul_operation_alm_vm['immo'])
        # Operations achats-ventes oblig
        if calcul_operation_alm_vm['oblig'] > 0:
            self.acheter_des_oblig(calcul_operation_alm_vm['oblig'])
        elif calcul_operation_alm_vm['oblig'] < 0:
            self.vendre_des_oblig(calcul_operation_alm_vm['oblig'])
        # Mise à jour de la treso
        self.portefeuille_treso["val_marche_fin"] = self.portefeuille_treso["val_marche_fin"] + calcul_operation_alm_vm['treso']
        self.calcul_alloc_strateg_crt()
        self.calcul_reserve_capitation(self.plus_moins_value_realised_oblig)
        self.calcul_provision_risque_exigibilite(t)

    
    def calcul_reserve_capitation(self, plus_ou_moins_value):
        """ 
            Fonction qui permet de calculer la reserve capitalisation après la vente d'obligations.
            Definition : https://assurance-vie.ooreka.fr/astuce/voir/503241/reserve-de-capitalisation (24/01/2021)
            La réserve de capitalisation est une réserve obligatoirement mise en place par les organismes d'assurance.
            Elle est alimentée par les plus-values réalisées sur les cessions d’obligations.
            L'objectif de la réserve de capitalisation est de lisser les résultats enregistrés sur les titres obligataires et de garantir aux assurés le rendement des contrats jusqu’à leur terme.
            La réserve de capitalisation fait partie de la marge de solvabilité.
            Cette réserve est alimentée par les plus-values constatées lors de la cession d'obligations et diminuée à hauteur des moins-values.
        
            :param plus_ou_moins_value: (Float) plus ou moins value latente des **obligations**

            :returns: None, mise à jour de la réserve de capitalisation de l'objet en cours.
        """
        self.reserve_capitalisation = max(0, self.reserve_capitalisation + plus_ou_moins_value)

    def calcul_provision_risque_exigibilite(self, t):
        """
            Fonction qui permet de calculer la provision pour risque d'exigibilite aka P.R.E.
            copy-paste de "argus de l'assurance"
            La provision pour risque d’exigibilité (PRE) a pour fonction de permettre à l’entreprise d’assurance de faire 
            face à ses engagements dans le cas de moins-value de certains actifs (C. assur., art. R. 332-20). 
            Une moins-value latente nette globale des placements concernés (action et immobilier) est constatée lorsque la valeur nette 
            comptable de ces placements est supérieure à leur valeur globale.
            La PRE est la moins value latente des actifs non ammortissables, dans ce modele : action et immobilier.
        
            :param t: (Int) année t de projection

            :returns: None, mise à jour de  provision pour risque d'exigibilite de l'objet portefeuille financier.
        """
        self.provision_risque_exigibilite = np.minimum(np.sum(self.portefeuille_action['pvl'] + self.portefeuille_action['mvl']) + np.sum(self.portefeuille_immo['pvl'] + self.portefeuille_immo['mvl']),0)

    def acheter_des_actions(self, montant_a_acheter):
        """
            Fonction permettant d'acheter des actions et de mettre le portfeuille action automatiquement à jour.

            :param montant_a_acheter: montant total des actions à acheter

            :returns: None, modification du portefeuille action de l'objet courant
        """
        # 2 - Calcul du nombre a acheter
        logging.info('Acheter des actions  : %s', montant_a_acheter)
        self.portefeuille_action["alloc"] = self.portefeuille_action["val_marche_fin"] / np.sum(self.portefeuille_action["val_marche_fin"])
        self.portefeuille_action["nb_unit_achat"] = montant_a_acheter * self.portefeuille_action["alloc"] / (self.portefeuille_action["val_marche_fin"]/self.portefeuille_action["nb_unit"])
        self.portefeuille_action["val_nc_fin"] = self.portefeuille_action["val_nc"] + montant_a_acheter *  self.portefeuille_action["alloc"]
        self.portefeuille_action["val_achat_fin"] = self.portefeuille_action["val_achat"] + montant_a_acheter *  self.portefeuille_action["alloc"]
        self.portefeuille_action["val_marche_fin"] = self.portefeuille_action["val_marche_fin"] + montant_a_acheter *  self.portefeuille_action["alloc"]
        self.portefeuille_action["nb_unit_fin"] = self.portefeuille_action["nb_unit"] + self.portefeuille_action["nb_unit_achat"]

    def acheter_des_immo(self, montant_a_acheter):
        """
            Fonction permettant d'acheter des actions et de mettre le portfeuille action automatiquement à jour.

            :param montant_a_acheter: (Float) montant total à acheter

            :returns: None, modificaiton du portefeuille immobilier
        """
        # 2 - Calcul du nombre a acheter
        logging.info('Acheter des immo  : %s', montant_a_acheter)
        self.portefeuille_immo["alloc"] = self.portefeuille_immo["val_marche_fin"] / np.sum(self.portefeuille_immo["val_marche_fin"])
        self.portefeuille_immo["nb_unit_achat"] = montant_a_acheter * self.portefeuille_immo["alloc"] / (self.portefeuille_immo["val_marche_fin"] / self.portefeuille_immo["nb_unit"])
        self.portefeuille_immo["val_nc_fin"] = self.portefeuille_immo["val_nc"] + montant_a_acheter * self.portefeuille_immo["alloc"]
        self.portefeuille_immo["val_achat_fin"] = self.portefeuille_immo["val_achat"] + montant_a_acheter * self.portefeuille_immo["alloc"]
        self.portefeuille_immo["val_marche_fin"] = self.portefeuille_immo["val_marche_fin"] + montant_a_acheter * self.portefeuille_immo["alloc"]
        self.portefeuille_immo["nb_unit_fin"] = self.portefeuille_immo["nb_unit"] + self.portefeuille_immo["nb_unit_achat"]

    def acheter_des_oblig(self, montant_a_acheter):
        """
            Fonction permettant d'acheter des actions et de mettre le portfeuille action automatiquement à jour.

            :param montant_a_acheter: (Float) montant total à acheter

            :returns: None, modificaiton du portefeuille obligation
        """
        # 2 - Calcul du nombre a acheter
        logging.info('Acheter des obligations  : %s', montant_a_acheter)
        self.portefeuille_oblig["nb_unit_achat"] = montant_a_acheter * self.portefeuille_oblig["nb_unit_ref"] / (self.portefeuille_oblig["val_marche_fin"] /self.portefeuille_oblig["nb_unit"])
        self.portefeuille_oblig["val_nc_fin"] = self.portefeuille_oblig["val_nc"] + montant_a_acheter * self.portefeuille_oblig["nb_unit_ref"]
        self.portefeuille_oblig["val_achat_fin"] = self.portefeuille_oblig["val_achat"] + montant_a_acheter * self.portefeuille_oblig["nb_unit_ref"]
        self.portefeuille_oblig["val_marche_fin"] = self.portefeuille_oblig["val_marche_fin"] + montant_a_acheter * self.portefeuille_oblig["nb_unit_ref"]
        self.portefeuille_oblig["nb_unit_fin"] = self.portefeuille_oblig["nb_unit"] + self.portefeuille_oblig["nb_unit_achat"]

    def calcul_des_pvl_action(self):
        """
            Calcul des plus values latentes sur les actions
        """
        temp = self.portefeuille_action.loc[self.portefeuille_action['val_marche_fin'] > self.portefeuille_action['val_nc_fin'],['val_nc_fin','val_marche_fin']]
        return np.sum(temp['val_marche_fin']-temp['val_nc_fin'])

    def calcul_des_pvl_immo(self):
        """
            Calcul des plus values latentes sur l'immobilier
        """
        temp = self.portefeuille_immo.loc[self.portefeuille_immo['val_marche_fin'] > self.portefeuille_immo['val_nc_fin'],['val_nc_fin','val_marche_fin']]
        return np.sum(temp['val_marche_fin']-temp['val_nc_fin'])

    def realiser_les_pvl_action(self, montant_a_vendre):
        """
            Cette fonction permet de réaliser les PVL action pour honorer le TMG, dans le cas ou le résultat total n'est pas 
            suffisant. Les flux de réalisation sont directement crédités à la trésorerie.
        """
        actions_en_pvl = self.portefeuille_action.loc[self.portefeuille_action["val_marche_fin"]>self.portefeuille_action["val_nc"]]
        actions_en_pvl["alloc"] = actions_en_pvl["val_marche"] / np.sum(actions_en_pvl["val_marche"]) 
        actions_en_pvl["nb_to_sold"] = (actions_en_pvl["alloc"] * (-1 * montant_a_vendre)) / (actions_en_pvl["val_marche"] / actions_en_pvl["nb_unit"])
        #actions_en_pvl["pct_to_sold"] = actions_en_pvl["nb_to_sold"] / actions_en_pvl["nb_unit"]
        self.portefeuille_treso["val_marche"] = np.sum((actions_en_pvl["val_achat"] - actions_en_pvl["val_nc"]) * actions_en_pvl["alloc"])
        # Actualisation des données de portefeuille
        actions_en_pvl["val_achat_fin"] = actions_en_pvl["val_achat"] * (1 - actions_en_pvl["alloc"])
        actions_en_pvl["val_marche_fin"] = actions_en_pvl["val_marche"] * (1 - actions_en_pvl["alloc"])
        actions_en_pvl["val_nc_fin"] = actions_en_pvl["val_nc"] *  (1 - actions_en_pvl["alloc"])
        actions_en_pvl["nb_unit_fin"] = actions_en_pvl["nb_unit"] * (1 - actions_en_pvl["alloc"])
        self.portefeuille_action.loc[self.portefeuille_action["val_marche_fin"]>self.portefeuille_action["val_nc"]] = actions_en_pvl

    def realiser_les_pvl_immo(self, montant_a_vendre):
        """
            Cette fonction permet de réaliser les PVL immo pour honorer le TMG, dans le cas ou le résultat total n'est pas 
            suffisant. Les flux de réalisation sont directement crédités à la trésorerie.
        """
        immo_en_pvl = self.portefeuille_immo.loc[self.portefeuille_immo["val_marche_fin"]>self.portefeuille_immo["val_nc"]]
        immo_en_pvl["alloc"] = immo_en_pvl["val_marche"] / np.sum(immo_en_pvl["val_marche"]) 
        immo_en_pvl["nb_to_sold"] = (immo_en_pvl["alloc"] * -1 * montant_a_vendre) / (immo_en_pvl["val_marche"] / immo_en_pvl["nb_unit"])
        #immo_en_pvl["pct_to_sold"] = immo_en_pvl["nb_to_sold"] / immo_en_pvl["nb_unit"]
        self.portefeuille_treso["val_marche"] = np.sum((immo_en_pvl["val_achat"] - immo_en_pvl["val_nc"]) * immo_en_pvl["alloc"])
        # Actualisation des données de portefeuille
        immo_en_pvl["val_achat_fin"] = immo_en_pvl["val_achat"] * (1 - immo_en_pvl["alloc"])
        immo_en_pvl["val_marche_fin"] = immo_en_pvl["val_marche"] * (1 - immo_en_pvl["alloc"])
        immo_en_pvl["val_nc_fin"] = immo_en_pvl["val_nc"] *  (1 - immo_en_pvl["alloc"])
        immo_en_pvl["nb_unit_fin"] = immo_en_pvl["nb_unit"] * (1 - immo_en_pvl["alloc"])
        self.portefeuille_immo.loc[self.portefeuille_immo["val_marche_fin"]>self.portefeuille_immo["val_nc"]] = immo_en_pvl

    def vendre_des_actions(self, montant_a_vendre):
        """
            Fonction permettant de vendre des actions et de mettre le portefeuille action automatiquement à jour.
            TODO : gérer le cas où le le nombre d'actif à vendre est supérieur au nombre d'actifs disponible

            :param montant_a_vendre: (Float) montant négatif représentant le montant de vente des actions

            :returns: None, modificaiton du portefeuille actions
        """
        logging.info('Vendre des actions  : %s', montant_a_vendre)
        self.portefeuille_action["alloc"] = self.portefeuille_action["val_marche_fin"] / np.sum(self.portefeuille_action["val_marche_fin"])
        self.portefeuille_action["nb_to_sold"] = (self.portefeuille_action["alloc"] * -1 * montant_a_vendre) / (self.portefeuille_action["val_marche_fin"] / self.portefeuille_action["nb_unit"])
        #self.portefeuille_action["pct_to_sold"] = self.portefeuille_action["nb_to_sold"] / self.portefeuille_action["nb_unit"]
        self.plus_moins_value_realised_action = np.sum((self.portefeuille_action["mvl"] - self.portefeuille_action["pvl"]) * self.portefeuille_action["alloc"])
        self.plus_moins_value_realised_total = self.plus_moins_value_realised_total + self.plus_moins_value_realised_action
        # Actualisation des données de portefeuille
        self.portefeuille_action["val_achat_fin"] = self.portefeuille_action["val_achat"] + montant_a_vendre * self.portefeuille_action["alloc"]
        self.portefeuille_action["val_marche_fin"] = self.portefeuille_action["val_marche_fin"]  + montant_a_vendre * self.portefeuille_action["alloc"]
        self.portefeuille_action["val_nc_fin"] = self.portefeuille_action["val_nc"] + montant_a_vendre * self.portefeuille_action["alloc"]
        self.portefeuille_action["nb_unit_fin"] = self.portefeuille_action["nb_unit"] - self.portefeuille_action["nb_to_sold"]
        #self.portefeuille_treso["val_marche"] = self.portefeuille_treso["val_marche"] + np.abs(montant_a_vendre)

    def vendre_des_immo(self, montant_a_vendre):
        """
            Fonction permettant de vendre des immo et de mettre le portefeuille action automatiquement à jour.
            TODO : gérer le cas où le le nombre d'actif à vendre est supérieur au nombre d'actifs disponible

            :param montant_a_vendre: montant total à vendre

            :returns: None, modificaiton du portefeuille immobilier
        """
        logging.info('Vendre des immo  : %s', montant_a_vendre)
        self.portefeuille_immo["alloc"] = self.portefeuille_immo["val_marche_fin"] / np.sum(self.portefeuille_immo["val_marche_fin"])
        self.portefeuille_immo["nb_to_sold"] = (self.portefeuille_immo["alloc"] * -1 * montant_a_vendre) / (self.portefeuille_immo["val_marche_fin"] / self.portefeuille_immo["nb_unit"])
        #self.portefeuille_immo["pct_to_sold"] = self.portefeuille_immo["nb_to_sold"] / self.portefeuille_immo["nb_unit"]
        self.plus_moins_value_realised_immo = np.sum((self.portefeuille_immo["pvl"]+self.portefeuille_immo["mvl"])*self.portefeuille_immo["alloc"])
        self.plus_moins_value_realised_total = self.plus_moins_value_realised_total + self.plus_moins_value_realised_immo
        # Actualisation des données de portefeuille
        self.portefeuille_immo["val_achat_fin"] = self.portefeuille_immo["val_achat"] + montant_a_vendre * self.portefeuille_immo["alloc"]
        self.portefeuille_immo["val_marche_fin"] = self.portefeuille_immo["val_marche_fin"] + montant_a_vendre * self.portefeuille_immo["alloc"]
        self.portefeuille_immo["val_nc_fin"] = self.portefeuille_immo["val_nc"] + montant_a_vendre * self.portefeuille_immo["alloc"]
        self.portefeuille_immo["nb_unit_fin"] = self.portefeuille_immo["nb_unit"] - self.portefeuille_immo["nb_to_sold"]
        #self.portefeuille_treso["val_marche"] = self.portefeuille_treso["val_marche"] + np.abs(montant_a_vendre)

    def vendre_des_oblig(self, montant_a_vendre):
        """
            Fonction permettant de vendre des immo et de mettre le portefeuille action automatiquement à jour.
            TODO : gérer le cas où le le nombre d'actif à vendre est supérieur au nombre d'actifs disponible

            :param montant_a_vendre: montant total à vendre

            :returns: None, modificaiton du portefeuille obligation
        """
        logging.info('Vendre des obligations  : %s', montant_a_vendre)
        self.portefeuille_oblig["alloc"] = self.portefeuille_oblig["val_marche_fin"] / np.sum(self.portefeuille_oblig["val_marche_fin"])
        self.portefeuille_oblig["nb_to_sold"] = (self.portefeuille_oblig["alloc"] * -1 * montant_a_vendre) / (self.portefeuille_oblig["val_marche_fin"] / self.portefeuille_oblig["nb_unit"])
        #self.portefeuille_oblig["pct_to_sold"] = self.portefeuille_oblig["nb_to_sold"] / self.portefeuille_oblig["nb_unit"]
        self.plus_moins_value_realised_oblig = np.sum((self.portefeuille_oblig["pvl"]+self.portefeuille_oblig["mvl"]) * self.portefeuille_oblig["alloc"])
        self.plus_moins_value_realised_total = self.plus_moins_value_realised_total + self.plus_moins_value_realised_oblig
        # Actualisation des données de portefeuille
        self.portefeuille_oblig["val_achat_fin"] = self.portefeuille_oblig["val_achat"] + montant_a_vendre * self.portefeuille_oblig["alloc"]
        self.portefeuille_oblig["val_marche_fin"] = self.portefeuille_oblig["val_marche_fin"] + montant_a_vendre * self.portefeuille_oblig["alloc"]
        self.portefeuille_oblig["val_nc_fin"] = self.portefeuille_oblig["val_nc"] + montant_a_vendre * self.portefeuille_oblig["alloc"]
        self.portefeuille_oblig["nb_unit_fin"] = self.portefeuille_oblig["nb_unit"] - self.portefeuille_oblig["nb_to_sold"]
        #self.portefeuille_treso["val_marche"] = self.portefeuille_treso["val_marche"] + np.abs(montant_a_vendre)

    def calcul_resultat_financier(self, tx_frais_val_marche, tx_frais_produits, tx_charges_reserve_capi):
        """
        Fonction de calcul du resultat financier : revenu + produit - frais_fin - var_rc

        :param tx_frais_val_marche: montant des frais de marché
        :param tx_frais_produits: montant des frais sur les produits financiers
        :param tx_charges_reserve_capi: montant des charges sur la réserve de capitalisation

        :returns: resultat financier.
        """
        self.calcul_alloc_strateg_crt()
        self.resultat_financier = np.sum(self.portefeuille_action["val_marche"] * self.portefeuille_action["div"]) \
                                + np.sum(self.portefeuille_immo["val_marche"] * self.portefeuille_immo["tx_loyer"]) \
                                + np.sum(self.portefeuille_oblig["val_marche"] * self.portefeuille_oblig["tx_coupon"]) \
                                + np.sum(self.portefeuille_oblig.loc[self.portefeuille_oblig['mat_res'] == 0,'nominal']) \
                                + self.plus_moins_value_realised_oblig \
                                + self.plus_moins_value_realised_action \
                                + self.plus_moins_value_realised_immo \
                                - tx_frais_val_marche * self.allocation_courante['total_vm_portfi'] \
                                - tx_charges_reserve_capi * self.reserve_capitalisation \
                                - tx_frais_produits * 0

    def calcul_tra(self):
        """
            Calcul du taux de rendement financier
        """
        placement_moyen = (np.sum(self.portefeuille_action["val_nc_fin"]) + np.sum(self.portefeuille_action["val_nc"]))/2 + \
                            (np.sum(self.portefeuille_immo["val_nc_fin"]) + np.sum(self.portefeuille_immo["val_nc"]))/2 + \
                                (np.sum(self.portefeuille_oblig["val_nc_fin"]) + np.sum(self.portefeuille_oblig["val_nc"]))/2
        if placement_moyen == 0:
            return 0
        else:
            return self.resultat_financier/placement_moyen

    def initialisation_ptf_financier(self):
        """
            Initialise le portefeuille financier pour une projection de l'année N.
            Le portefeuille en fin d'année de projection N-1 devient le portefeuille input pour la projection de l'année N

            :param : None

            :returns: None
        """
        # initialisation action
        self.portefeuille_action = self.portefeuille_action[['num_mp', 'val_marche_fin', 'val_nc_fin', 'val_achat_fin', 'presence', 'cessible',
       'nb_unit_fin', 'dur_det', 'pdd', 'num_index', 'div', 'ind_invest', 'nb_unit_ref']]
        self.portefeuille_action = self.portefeuille_action.rename(columns={"val_marche_fin": "val_marche", "val_nc_fin": "val_nc",
        "val_achat_fin": "val_achat", "nb_unit_fin": "nb_unit"})
        # initialisation immo
        self.portefeuille_immo = self.portefeuille_immo[['num_mp', 'val_marche_fin', 'val_nc_fin', 'val_achat_fin', 'presence', 'cessible',
       'nb_unit_fin', 'dur_det', 'pdd', 'num_index', 'tx_loyer', 'ind_invest', 'nb_unit_ref']]
        self.portefeuille_immo = self.portefeuille_immo.rename(columns={"val_marche_fin": "val_marche", "val_nc_fin": "val_nc",
        "val_achat_fin": "val_achat", "nb_unit_fin": "nb_unit"})
        # initialisation oblig
        self.portefeuille_oblig = self.portefeuille_oblig.loc[self.portefeuille_oblig['mat_res'] != 0,:] 
        self.portefeuille_oblig = self.portefeuille_oblig[['num_mp', 'val_marche_fin', 'val_nc_fin', 'val_achat_fin', 'presence', 'cessible',
       'nb_unit_fin', 'dur_det', 'nominal', 'tx_coupon', 'par', 'mat_res', 'type', 'rating', 'zspread', 'cc', 'sd', 'nb_unit_ref']]
        self.portefeuille_oblig = self.portefeuille_oblig.rename(columns={"val_marche_fin": "val_marche", "val_nc_fin": "val_nc",
        "val_achat_fin": "val_achat", "nb_unit_fin": "nb_unit"})
        # initialisation treso
        self.portefeuille_treso = self.portefeuille_treso[['num_mp', 'val_nc', 'val_marche_fin', 't', 'rdt']]
        self.portefeuille_treso = self.portefeuille_treso.rename(columns={"val_marche_fin": "val_marche"})